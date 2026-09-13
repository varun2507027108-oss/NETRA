package netra.core

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Base64
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * NetraYoloGoldenTest — on-device parity vs core/fixtures/yolo/golden_v1.json
 * (recorded by tools/record_yolo_golden.py v2; contract: input [1,3,640,640]
 * NCHW caller-divided-by-255; output [1,9,8400], rows 0-3 normalized
 * cx,cy,w,h, rows 4-8 post-sigmoid; Kotlin owns conf+NMS).
 *
 * Stages:
 *   1. rawTensorParity    — recorded input bytes -> runRaw -> recorded
 *                           output bytes (pins the graph contract on silicon)
 *   2. preprocessParity   — Kotlin letterbox+preprocess vs recorded tensor
 *                           (pins the preprocessing; Android-vs-PIL bilinear
 *                           LSB differences are inside tolerance)
 *   3. decodedParity      — detect() vs recorded decoded list (the real gate)
 *   4. perfStats          — interpreter init / first inference / warm mean
 *
 * Fixture + image live in androidTest assets (copied from core/fixtures/yolo).
 */
@RunWith(AndroidJUnit4::class)
class NetraYoloGoldenTest {

    private val testCtx: Context
        get() = InstrumentationRegistry.getInstrumentation().context
    private val appCtx: Context
        get() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun golden(): JSONObject = JSONObject(
        testCtx.assets.open("yolo/golden_v1.json").bufferedReader().readText())

    private fun goldenBitmap(): Bitmap =
        testCtx.assets.open("yolo/golden_input.png").use {
            BitmapFactory.decodeStream(it)
                ?: error("golden_input.png undecodable")
        }

    private fun b64Floats(b64: String): FloatArray {
        val raw = Base64.decode(b64, Base64.DEFAULT)
        val buf = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
        return FloatArray(raw.size / 4) { buf.float }
    }

    private fun cfg(g: JSONObject): YoloConfig {
        val labels = g.getJSONArray("class_labels")
        val t = g.getJSONObject("thresholds")
        return YoloConfig(
            inputSize = 640,
            classCount = labels.length(),
            classLabels = List(labels.length()) { labels.getString(it) },
            confThreshold = t.getDouble("conf").toFloat(),
            iouThreshold = t.getDouble("iou").toFloat(),
            graphNormalizesInput = g.getBoolean("graph_normalizes_input"),
        )
    }

    private fun iou(x1: Float, y1: Float, w1: Float, h1: Float,
                    x2: Float, y2: Float, w2: Float, h2: Float): Float {
        val ax = max(x1, x2); val ay = max(y1, y2)
        val bx = min(x1 + w1, x2 + w2); val by = min(y1 + h1, y2 + h2)
        val inter = max(0f, bx - ax) * max(0f, by - ay)
        val union = w1 * h1 + w2 * h2 - inter
        return if (union <= 0f) 0f else inter / union
    }

    @Test
    fun rawTensorParity() {
        val g = golden()
        NetraYolo.fromAsset(appCtx, "yolo26n_roi.tflite", cfg(g)).use { yolo ->
            val input = b64Floats(g.getJSONObject("input").getString("values_b64"))
            val expected = b64Floats(g.getJSONObject("output").getString("values_b64"))
            val buf = ByteBuffer.allocateDirect(input.size * 4)
                .order(ByteOrder.nativeOrder())
            for (v in input) buf.putFloat(v)
            val out = yolo.runRaw(buf)
            var maxDiff = 0f
            var i = 0
            for (ch in out[0].indices) {
                for (a in out[0][ch].indices) {
                    val d = abs(out[0][ch][a] - expected[i++])
                    if (d > maxDiff) maxDiff = d
                }
            }
            println("RAW_TENSOR_MAX_ABS_DIFF=$maxDiff")
            assertTrue(
                "raw tensor max abs diff $maxDiff exceeds 1e-2 — " +
                    "device runtime deviates from the pinned contract",
                maxDiff <= 1e-2f)
        }
    }

    @Test
    fun preprocessParity() {
        val g = golden()
        NetraYolo.fromAsset(appCtx, "yolo26n_roi.tflite", cfg(g)).use { yolo ->
            val expected = b64Floats(g.getJSONObject("input").getString("values_b64"))
            val (boxed, _) = yolo.letterbox(goldenBitmap())
            val got = yolo.preprocess(boxed)
            got.rewind()
            val n = expected.size
            var sum = 0.0
            var over = 0
            var maxd = 0f
            for (i in 0 until n) {
                val d = abs(got.float - expected[i])
                sum += d
                if (d > maxd) maxd = d
                if (d > 0.02f) over++
            }
            val mean = sum / n
            val fracOver = over.toDouble() / n
            println(
                "PREPROCESS_MEAN_ABS_DIFF=$mean " +
                    "PCT_OVER_0.02=${"%.2f".format(fracOver * 100)} MAX=$maxd")
            // Gates calibrated on measured evidence (CPH2467, LiteRT 1.0.1):
            // mean 0.0039, pct>0.02 4.53%, max 0.118. Android Skia bilinear
            // vs PIL triangle filter differ at 2x downscale at edges only.
            // mean/pct bound systematic errors (wrong scale/crop/channel/pad
            // blow them up 10-100x); max bounds legitimate hard-edge phase
            // differences between two valid kernels (theoretical ~0.5).
            assertTrue("mean abs diff $mean > 0.01", mean <= 0.01)
            assertTrue("fraction over 0.02 is $fracOver > 0.05", fracOver <= 0.05)
            assertTrue("max abs diff $maxd > 0.5", maxd <= 0.5f)
        }
    }

    @Test
    fun decodedParity() {
        val g = golden()
        NetraYolo.fromAsset(appCtx, "yolo26n_roi.tflite", cfg(g)).use { yolo ->
            val dets = yolo.detect(goldenBitmap())
            val rec = g.getJSONArray("decoded")
            println("DETECTED=${dets.size} RECORDED=${rec.length()}")
            // Exact decode of the recorded tensor is enforced in Python
            // (core/tests/test_yolo_golden.py::test_decode_reproduces_recorded).
            // This device gate bounds end-to-end sensitivity to cross-platform
            // resize-kernel noise (measured preprocess mean 0.0039, 4.5% of
            // pixels > 0.02): near-threshold detections may flip, so count is
            // +/-1 and matching is tiered by recorded confidence.
            assertTrue(
                "detection count ${dets.size} vs recorded ${rec.length()} differs by > 1",
                abs(dets.size - rec.length()) <= 1)

            fun boxOf(r: JSONObject): FloatArray = floatArrayOf(
                r.getDouble("x").toFloat(), r.getDouble("y").toFloat(),
                r.getDouble("w").toFloat(), r.getDouble("h").toFloat())

            // near-threshold: may flip under cross-platform resize noise
            // (measured on CPH2467/LiteRT: drift 0.007 @ 0.93 -> 0.154 @ 0.44;
            //  flip line set above the observed flip zone)
            for (i in 0 until rec.length()) {
                val r = rec.getJSONObject(i)
                val rs = r.getDouble("score").toFloat()
                if (rs < 0.55f) continue
                val rb = boxOf(r)
                val cand = dets.filter { it.labelIndex == r.getInt("label") }
                    .maxByOrNull { iou(it.x, it.y, it.w, it.h, rb[0], rb[1], rb[2], rb[3]) }
                val candIoU = cand?.let {
                    iou(it.x, it.y, it.w, it.h, rb[0], rb[1], rb[2], rb[3])
                } ?: -1f
                val candScore = cand?.score ?: -1f
                println("MATCH i=$i rec_score=$rs cand_score=$candScore cand_iou=$candIoU")
                assertTrue(
                    "recorded box $r has no device match " +
                        "(best candidate score=$candScore iou=$candIoU)",
                    cand != null && candIoU >= 0.85f && abs(candScore - rs) <= 0.08f)
            }
            // Anti-hallucination: every confident device box must correspond
            // to a recorded box.
            for (d in dets.filter { it.score >= 0.75f }) {
                val ok = (0 until rec.length()).any { j ->
                    val r = rec.getJSONObject(j)
                    if (r.getInt("label") != d.labelIndex ||
                        r.getDouble("score").toFloat() < 0.35f) return@any false
                    val rb = boxOf(r)
                    iou(d.x, d.y, d.w, d.h, rb[0], rb[1], rb[2], rb[3]) >= 0.85f
                }
                assertTrue(
                    "device box has no recorded counterpart: " +
                        "label=${d.label} score=${d.score} x=${d.x} y=${d.y} " +
                        "w=${d.w} h=${d.h}", ok)
            }
        }
    }

    @Test
    fun perfStats() {
        val g = golden()
        val src = goldenBitmap()
        val t0 = System.nanoTime()
        val yolo = NetraYolo.fromAsset(appCtx, "yolo26n_roi.tflite", cfg(g))
        val t1 = System.nanoTime()
        yolo.detect(src)                       // warmup incl. first inference
        val t2 = System.nanoTime()
        val times = mutableListOf<Long>()
        repeat(10) {
            val s = System.nanoTime()
            yolo.detect(src)
            times.add(System.nanoTime() - s)
        }
        yolo.close()
        println(
            "PERF_INIT_MS=${(t1 - t0) / 1_000_000} " +
                "FIRST_DETECT_MS=${(t2 - t1) / 1_000_000} " +
                "WARM_MEAN_MS=${times.average() / 1_000_000} " +
                "WARM_MAX_MS=${times.max() / 1_000_000}")
    }
}
