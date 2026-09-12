package netra.core

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import org.json.JSONObject
import org.tensorflow.lite.Interpreter
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import kotlin.math.exp
import kotlin.math.roundToInt

/**
 * NETRA on-device ROI detector — model round 1, contract pinned by
 * core/fixtures/yolo/golden_v1.json (record_yolo_golden.py v2):
 *
 *   input : [1,3,640,640] float32 NCHW — CALLER divides by 255
 *           (the graph does NOT normalize internally)
 *   output: [1,9,8400] float32 native — rows 0-3 = cx,cy,w,h NORMALIZED [0,1]
 *           over the 640x640 canvas; rows 4-8 = post-sigmoid class scores.
 *           LiteRT export has NO embedded NMS — Kotlin owns conf-gate +
 *           per-class NMS + letterbox inversion.
 *
 * Classes (order fixed by model.names, served via vision_config.json):
 * PACKAGE, PDP, PRICE, BARCODE, BOP.
 * Emission space: CAPTURE space (1600px resize-once frame) — same space as
 * ML Kit tokens and s5 K-NN. Coordinate-space rule: never violated.
 * Export fidelity vs .pt on identical tensor: 0.0152 px (boxes), 6e-6 (scores).
 * ZERO statutory logic in this file. ROI geometry only.
 */
class NetraYolo(
    private val interpreter: Interpreter,
    val cfg: YoloConfig,
) : java.io.Closeable {

    private val outShape: IntArray = interpreter.getOutputTensor(0).shape()
    private val channels: Int = outShape[1]   // 4 + nc = 9
    private val anchors: Int = outShape[2]    // 8400 @ imgsz 640

    init {
        require(outShape.size == 3 && outShape[0] == 1) {
            "unexpected output shape ${outShape.contentToString()}"
        }
        require(channels == 4 + cfg.classCount) {
            "model reports $channels channels but config says 4+${cfg.classCount}"
        }
        if (cfg.classLabels.isNotEmpty()) {
            require(cfg.classLabels.size == cfg.classCount) { "classLabels size != classCount" }
        }
    }

    companion object {
        fun fromAsset(ctx: Context, assetPath: String, cfg: YoloConfig): NetraYolo {
            val model: MappedByteBuffer = ctx.assets.openFd(assetPath).use { fd ->
                fd.createInputStream().channel.map(
                    FileChannel.MapMode.READ_ONLY, fd.startOffset, fd.declaredLength)
            }
            val opts = Interpreter.Options().apply { setNumThreads(4) }
            return NetraYolo(Interpreter(model, opts), cfg)
        }
    }

    data class LetterboxMeta(val gain: Float, val padX: Float, val padY: Float)

    data class RoiBox(
        val labelIndex: Int,
        val label: String,
        val score: Float,
        /** top-left + size in CAPTURE space (1600px resize-once frame) */
        val x: Float, val y: Float, val w: Float, val h: Float,
    )

    fun detect(src: Bitmap): List<RoiBox> {
        val (boxed, meta) = letterbox(src)
        val raw = Array(1) { Array(channels) { FloatArray(anchors) } }
        interpreter.run(preprocess(boxed), raw)
        return decode(raw[0], meta)
    }

    /** Golden-test hook: feed recorded input, return raw [1][9][8400]. */
    fun runRaw(input: ByteBuffer): Array<Array<FloatArray>> {
        input.rewind()
        val raw = Array(1) { Array(channels) { FloatArray(anchors) } }
        interpreter.run(input, raw)
        return raw
    }

    /**
     * NCHW [1,3,640,640]: three channel planes (R, G, B), each H*W row-major.
     * graphNormalizesInput=false per pinned contract — we divide by 255 here.
     */
    fun preprocess(boxed: Bitmap): ByteBuffer {
        val w = boxed.width; val h = boxed.height
        val px = IntArray(w * h)
        boxed.getPixels(px, 0, w, 0, 0, w, h)
        val buf = ByteBuffer.allocateDirect(w * h * 3 * 4).order(ByteOrder.nativeOrder())
        val scale = if (cfg.graphNormalizesInput) 1f else 1f / 255f
        for (shift in intArrayOf(16, 8, 0)) {
            for (v in px) buf.putFloat(((v shr shift) and 0xFF) * scale)
        }
        buf.rewind()
        return buf
    }

    internal fun letterbox(src: Bitmap): Pair<Bitmap, LetterboxMeta> {
        val s = cfg.inputSize
        val gain = minOf(s.toFloat() / src.width, s.toFloat() / src.height)
        val nw = (src.width * gain).roundToInt().coerceIn(1, s)
        val nh = (src.height * gain).roundToInt().coerceIn(1, s)
        // int division on purpose — matches the Python recorder exactly
        val padX = (s - nw) / 2
        val padY = (s - nh) / 2
        val out = Bitmap.createBitmap(s, s, Bitmap.Config.ARGB_8888)
        Canvas(out).apply {
            drawColor(Color.rgb(cfg.padGray, cfg.padGray, cfg.padGray))
            drawBitmap(Bitmap.createScaledBitmap(src, nw, nh, true), padX.toFloat(), padY.toFloat(), null)
        }
        return out to LetterboxMeta(gain, padX.toFloat(), padY.toFloat())
    }

    fun decode(rows: Array<FloatArray>, meta: LetterboxMeta): List<RoiBox> {
        val n = rows[0].size
        val s = cfg.inputSize.toFloat()
        // Contract says post-sigmoid; full-scan guard protects a future re-export.
        var sigmoidNeeded = false
        outer@ for (a in 0 until n) {
            for (c in 4 until channels) {
                val v = rows[c][a]
                if (v < 0f || v > 1f) { sigmoidNeeded = true; break@outer }
            }
        }
        val score: (Float) -> Float = if (sigmoidNeeded) { x -> 1f / (1f + exp(-x)) } else { it }

        val cands = ArrayList<RoiBox>(64)
        for (a in 0 until n) {
            var bestIdx = -1; var best = 0f
            for (c in 4 until channels) {
                val sc = score(rows[c][a])
                if (sc > best) { best = sc; bestIdx = c - 4 }
            }
            if (bestIdx < 0 || best < cfg.confThreshold) continue
            // rows 0-3 NORMALIZED [0,1] over the canvas — scale to letterbox px
            val cx = rows[0][a] * s
            val cy = rows[1][a] * s
            val w = rows[2][a] * s
            val h = rows[3][a] * s
            cands += RoiBox(
                labelIndex = bestIdx, label = cfg.label(bestIdx), score = best,
                x = (cx - w * 0.5f - meta.padX) / meta.gain,
                y = (cy - h * 0.5f - meta.padY) / meta.gain,
                w = w / meta.gain, h = h / meta.gain,
            )
        }
        // No clamping here on purpose: golden parity compares unclamped boxes;
        // capture-space clamping happens at the scan_tokens contract layer.
        return nmsPerClass(cands)
    }

    private fun nmsPerClass(dets: List<RoiBox>): List<RoiBox> {
        val out = ArrayList<RoiBox>()
        for (group in dets.groupBy { it.labelIndex }.values) {
            val kept = ArrayList<RoiBox>()
            for (d in group.sortedByDescending { it.score }) {
                if (kept.none { iou(d, it) > cfg.iouThreshold }) kept += d
                if (kept.size >= cfg.maxDetectionsPerClass) break
            }
            out += kept
        }
        return out.sortedByDescending { it.score }
    }

    private fun iou(a: RoiBox, b: RoiBox): Float {
        val x1 = maxOf(a.x, b.x); val y1 = maxOf(a.y, b.y)
        val x2 = minOf(a.x + a.w, b.x + b.w); val y2 = minOf(a.y + a.h, b.y + b.h)
        val inter = (x2 - x1).coerceAtLeast(0f) * (y2 - y1).coerceAtLeast(0f)
        val union = a.w * a.h + b.w * b.h - inter
        return if (union <= 0f) 0f else inter / union
    }

    override fun close() = interpreter.close()
}

data class YoloConfig(
    val inputSize: Int = 640,
    val classCount: Int = 5,
    val classLabels: List<String> = emptyList(), // from vision_config.json only
    val confThreshold: Float = 0.25f,
    val iouThreshold: Float = 0.45f,
    val maxDetectionsPerClass: Int = 20,
    val graphNormalizesInput: Boolean = false,   // pinned by golden_v1.json
    val padGray: Int = 114,
) {
    fun label(i: Int): String = classLabels.getOrElse(i) { "class_$i" }

    companion object {
        /** Served from Python via vision_config.json — single source of law. */
        fun fromVisionConfig(json: JSONObject): YoloConfig {
            val y = json.getJSONObject("yolo")
            val boxSpace = y.optString("output_box_space", "normalized_0_1")
            require(boxSpace == "normalized_0_1") {
                "unsupported output_box_space '$boxSpace' — decoder implements normalized_0_1"
            }
            val labels = y.getJSONArray("class_labels")
            return YoloConfig(
                inputSize = y.getInt("input_size"),
                classCount = y.getInt("num_classes"),
                classLabels = List(labels.length()) { labels.getString(it) },
                confThreshold = y.getDouble("conf_threshold").toFloat(),
                iouThreshold = y.getDouble("iou_threshold").toFloat(),
                maxDetectionsPerClass = y.optInt("max_detections_per_class", 20),
                graphNormalizesInput = y.optBoolean("graph_normalizes_input", false),
                padGray = y.optInt("pad_gray", 114),
            )
        }
    }
}
