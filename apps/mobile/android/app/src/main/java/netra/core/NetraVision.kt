package netra.core

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Base64
import org.json.JSONObject
import org.opencv.android.OpenCVLoader
import org.opencv.android.Utils
import org.opencv.core.Core
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.core.MatOfDouble
import org.opencv.core.MatOfPoint2f
import org.opencv.core.MatOfPoint3f
import org.opencv.core.Point3
import org.opencv.imgproc.Imgproc
import org.opencv.calib3d.Calib3d
import org.opencv.objdetect.ArucoDetector
import org.opencv.objdetect.DetectorParameters
import org.opencv.objdetect.Objdetect
import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.max
import kotlin.math.sqrt

/**
 * NETRA Kotlin vision pre-pass — the B1 half of stages 1 and 3.
 *
 * LAW: every threshold lives in netra_core/vision_config.json (served by
 * the Python core via the channel `vision_config` method, generated from
 * config.py). This file hardcodes NOTHING statutory. If a number appears
 * here, it is a bug.
 *
 * Provides:
 *   prepass(imageB64, optionsJson) -> JSON {
 *     quality:   {ok, laplacian_var, glare_pct, prompts[], glare_bbox?},
 *     geometry:  {shape?, mm_per_px?, pda_cm2?, pda_method?,
 *                 marker_detected, tilt_deg?, warnings[]}
 *   }
 *   Contract: same shapes as scan_tokens' quality/geometry blocks (§14),
 *   same coordinate space as the SUBMITTED image (bboxes map back from
 *   the downscaled working frame).
 *
 * Failure semantics mirror the Python stages: uncertain -> absent +
 * warning, never a crash. OpenCV init failure -> in-band error envelope.
 */
object NetraVision {

    private var inited = false
    private var cfg: JSONObject? = null

    fun ensureOpenCv() {
        if (!inited) {
            if (!OpenCVLoader.initLocal()) {
                throw IllegalStateException("OpenCV native init failed")
            }
            inited = true
        }
    }

    fun loadConfig(configJson: String) {
        cfg = JSONObject(configJson)
    }

    private fun c(name: String): Double = cfg!!.optDouble(name)
    private fun cInt(name: String): Int = cfg!!.optInt(name)

    // ---------------------------------------------------------------- API
    fun prepass(imageB64: String, optionsJson: String = "{}"): String {
        try {
            ensureOpenCv()
        } catch (e: Exception) {
            return errorEnvelope("INTERNAL", "OpenCV init failed: ${e.message}")
        }
        if (cfg == null) {
            return errorEnvelope("STAGE_FAILURE", "vision config not loaded from Python core")
        }
        val opts = JSONObject(optionsJson)

        val raw = Base64.decode(imageB64, Base64.DEFAULT)
        val bmp = BitmapFactory.decodeByteArray(raw, 0, raw.size)
            ?: return errorEnvelope("DECODE_ERROR", "undecodable image bytes")
        val W = bmp.width
        val H = bmp.height

        // ---- working scale: analyze downscaled, report in full-res space
        val longSide = maxOf(W, H)
        val workScale = if (longSide > 1600) 1600.0 / longSide else 1.0
        val wW = max(1, (W * workScale).toInt())
        val wH = max(1, (H * workScale).toInt())
        val work = Bitmap.createScaledBitmap(bmp, wW, wH, true)
        val bgr = Mat()
        Utils.bitmapToMat(work, bgr)          // RGBA actually; convert:
        Imgproc.cvtColor(bgr, bgr, Imgproc.COLOR_RGBA2BGR)
        val gray = Mat()
        Imgproc.cvtColor(bgr, gray, Imgproc.COLOR_BGR2GRAY)

        val quality = qualityGate(gray, W, H, workScale)
        val geometry = calibrate(bgr, gray, opts, W, H, workScale)

        return JSONObject()
            .put("quality", quality)
            .put("geometry", geometry)
            .toString()
    }

    // ------------------------------------------------------------- stage 1
    private fun qualityGate(gray: Mat, W: Int, H: Int, scale: Double):
            JSONObject {
        val lap = Mat()
        Imgproc.Laplacian(gray, lap, CvType.CV_64F)
        val mean = MatOfDouble()
        val stddev = MatOfDouble()
        Core.meanStdDev(lap, mean, stddev)
        val lapVar = stddev.get(0, 0)[0] * stddev.get(0, 0)[0]

        val thresh = Mat()
        Imgproc.threshold(
            gray, thresh, c("GLARE_PIXEL_MAX"), 255.0, Imgproc.THRESH_BINARY)
        val glarePx = Core.countNonZero(thresh)
        val glarePct = 100.0 * glarePx / (gray.rows() * gray.cols())

        val prompts = org.json.JSONArray()
        var ok = true
        if (lapVar < c("LAPLACIAN_VAR_MIN")) {
            ok = false
            prompts.put("Hold steady — frame is blurred")
        }
        var glareBbox: JSONObject? = null
        if (glarePct > c("GLARE_AREA_PCT_MAX")) {
            ok = false
            prompts.put("Tilt 10–15° to move glare off the label")
            // largest bright contour, reported in full-res space
            val contours = ArrayList<org.opencv.core.MatOfPoint>()
            Imgproc.findContours(
                thresh, contours, Mat(), Imgproc.RETR_EXTERNAL,
                Imgproc.CHAIN_APPROX_SIMPLE)
            if (contours.isNotEmpty()) {
                val biggest = contours.maxByOrNull {
                    Imgproc.contourArea(it)
                }!!
                val r = Imgproc.boundingRect(biggest)
                glareBbox = JSONObject()
                    .put("x", (r.x / scale).toInt())
                    .put("y", (r.y / scale).toInt())
                    .put("w", (r.width / scale).toInt())
                    .put("h", (r.height / scale).toInt())
            }
        }
        val q = JSONObject()
            .put("ok", ok)
            .put("laplacian_var", lapVar)
            .put("glare_pct", glarePct)
            .put("prompts", prompts)
        if (glareBbox != null) q.put("glare_bbox",
            org.json.JSONArray().put(glareBbox.getInt("x"))
                .put(glareBbox.getInt("y"))
                .put(glareBbox.getInt("w"))
                .put(glareBbox.getInt("h")))
        return q
    }

    // ------------------------------------------------------------- stage 3
    private fun calibrate(bgr: Mat, gray: Mat, opts: JSONObject,
                          W: Int, H: Int, scale: Double): JSONObject {
        val warnings = org.json.JSONArray()
        val g = JSONObject()
            .put("marker_detected", false)

        // ---- ArUco detection (dictionary from the shared config)
        val dictId = when (cfg!!.optString("ARUCO_DICT")) {
            "DICT_4X4_50" -> Objdetect.DICT_4X4_50
            "DICT_4X4_100" -> Objdetect.DICT_4X4_100
            else -> Objdetect.DICT_4X4_50
        }
        val dictionary = Objdetect.getPredefinedDictionary(dictId)
        val params = DetectorParameters()
        val corners = ArrayList<Mat>()
        val ids = Mat()
        val rejected = ArrayList<Mat>()
        val detector = ArucoDetector(dictionary, params)
        detector.detectMarkers(gray, corners, ids, rejected)

        var markerSideMm = c("ARUCO_MARKER_MM")
        if (opts.has("marker_side_mm")) {
            markerSideMm = opts.optDouble("marker_side_mm")
        }

        if (ids.empty()) {
            warnings.put("no fiducial in frame — hold the calibration card "
                    + "flat against the package")
            g.put("warnings", warnings)
            return finishGeometry(g, opts, warnings)
        }

        // largest marker (by contour area) = the card
        var bestIdx = 0
        var bestArea = -1.0
        for (i in 0 until corners.size) {
            val a = Imgproc.contourArea(corners[i])
            if (a > bestArea) { bestArea = a; bestIdx = i }
        }
        val quad = corners[bestIdx]           // 4x1x2, TL TR BR BL
        val pts = MatOfPoint2f()
        quad.reshape(2, 4).convertTo(pts, CvType.CV_32F)

        // ---- homography planar scale (focal-invariant), at working res
        val half = (markerSideMm / 2.0)
        val objPts = MatOfPoint3f(
            Point3(-half, -half, 0.0), Point3(half, -half, 0.0),
            Point3(half, half, 0.0), Point3(-half, half, 0.0))
        val HMat = Calib3d.findHomography(objToImg(objPts), pts, 0)
        if (HMat.empty()) {
            warnings.put("degenerate marker geometry")
            g.put("warnings", warnings)
            return finishGeometry(g, opts, warnings)
        }
        // mm_per_px from the average linear scale of H's 2x2 block
        val h00 = HMat.get(0, 0)[0]; val h01 = HMat.get(0, 1)[0]
        val h10 = HMat.get(1, 0)[0]; val h11 = HMat.get(1, 1)[0]
        val s1 = sqrt(h00 * h00 + h10 * h10)          // px per mm (x dir)
        val s2 = sqrt(h01 * h01 + h11 * h11)          // px per mm (y dir)
        val pxPerMm = (s1 + s2) / 2.0
        if (pxPerMm <= 0.0) {
            warnings.put("degenerate marker scale")
            g.put("warnings", warnings)
            return finishGeometry(g, opts, warnings)
        }
        var mmPerPx = 1.0 / pxPerMm                    // at WORKING scale
        mmPerPx /= scale                              // to FULL-RES space

        // ---- solvePnP cross-check + tilt (approximate intrinsics)
        val focal = 1.2 * maxOf(W, H)                 // f = 1.2 * long side
        val K = Mat.eye(3, 3, CvType.CV_64F)
        K.put(0, 0, focal); K.put(1, 1, focal)
        K.put(0, 2, W / 2.0); K.put(1, 2, H / 2.0)

        // marker corners at FULL resolution
        val ptsFullArr = pts.toArray().map { org.opencv.core.Point(it.x / scale, it.y / scale) }
        val ptsFull = MatOfPoint2f(*ptsFullArr.toTypedArray())

        val rvec = Mat(); val tvec = Mat()
        val ok = Calib3d.solvePnP(objPts, ptsFull, K, MatOfDouble(),
            rvec, tvec, false, Calib3d.SOLVEPNP_IPPE)
        var tiltDeg: Double? = null
        if (ok) {
            val r = Mat()
            Calib3d.Rodrigues(rvec, r)
            // Plane normal in camera coords is R * [0, 0, 1]^T, which is third column of R: (r02, r12, r22)
            val rx = r.get(0, 2)[0]
            val ry = r.get(1, 2)[0]
            val rz = r.get(2, 2)[0]
            val norm = sqrt(rx * rx + ry * ry + rz * rz)
            val zComponent = if (norm > 0.0) abs(rz / norm) else abs(rz)
            tiltDeg = Math.toDegrees(acos(zComponent.coerceIn(-1.0, 1.0)))

            val depth = tvec.get(2, 0)[0]
            val pnpMmPerPx = depth / focal
            val disagree = abs(pnpMmPerPx - mmPerPx) / mmPerPx
            if (disagree > c("SOLVEPNP_SCALE_TOLERANCE")) {
                warnings.put(String.format(
                    "solvePnP scale disagrees by %.0f%% — homography " +
                    "scale kept", disagree * 100))
            }
            if (tiltDeg > c("MAX_TILT_DEG")) {
                warnings.put(String.format(
                    "camera tilt %.0f° — hold the card square to the " +
                    "lens for best accuracy", tiltDeg))
            }
        }

        g.put("marker_detected", true)
        g.put("mm_per_px", round6(mmPerPx))
        g.put("marker_id", ids.get(bestIdx, 0)[0].toInt())
        if (tiltDeg != null) g.put("tilt_deg", Math.round(tiltDeg * 10) / 10.0)
        g.put("warnings", warnings)
        return finishGeometry(g, opts, warnings)
    }

    // PDA from inspector dims (mirrors _pda_from_options in Python)
    private fun finishGeometry(g: JSONObject, opts: JSONObject,
                               warnings: org.json.JSONArray): JSONObject {
        val shape = opts.optString("shape_hint", "")
        val h = opts.optDouble("package_height_cm", 0.0)
        val w = opts.optDouble("package_width_cm", 0.0)
        val d = opts.optDouble("package_diameter_cm", 0.0)
        val total = opts.optDouble("total_surface_cm2", 0.0)
        var pda: Double? = null
        var method = ""
        when (shape) {
            "cylindrical", "bottle" ->
                if (h > 0 && d > 0) {
                    pda = c("PDA_CYL_COEF") * h * Math.PI * d; method = "inspector-dims"
                }
            "rectangular", "pouch" ->
                if (h > 0 && w > 0) { pda = h * w; method = "inspector-dims" }
            else -> if (total > 0) {
                pda = c("PDA_CYL_COEF") * total; method = "inspector-dims"
            } else if (h > 0 && w > 0) {
                pda = h * w; method = "inspector-dims"
            }
        }
        if (pda != null) {
            val lo = cfg!!.optJSONArray("PDA_SANITY_CM2").optDouble(0)
            val hi = cfg!!.optJSONArray("PDA_SANITY_CM2").optDouble(1)
            if (pda in lo..hi) {
                g.put("pda_cm2", Math.round(pda * 100.0) / 100.0)
                g.put("pda_method", method)
            } else {
                warnings.put(String.format(
                    "PDA %.0f cm² outside sanity range — ignored", pda))
            }
        }
        return g
    }

    private fun objToImg(obj: MatOfPoint3f): MatOfPoint2f {
        val ptsArray = obj.toArray()
        val src = ptsArray.map { org.opencv.core.Point(it.x, it.y) }
        return MatOfPoint2f(*src.toTypedArray())
    }

    private fun round6(v: Double): Double = Math.round(v * 1e6) / 1e6

    private fun errorEnvelope(code: String, msg: String): String =
        JSONObject().put("error",
            JSONObject().put("code", code).put("message", msg)).toString()
}
