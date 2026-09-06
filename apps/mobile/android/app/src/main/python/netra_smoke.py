"""NETRA Android spike — one call, full environment report (Step 0 of
docs/ANDROID_INTEGRATION.md).

Copy into the Flutter app's Chaquopy python source dir
(app/src/main/python/). Run from Kotlin (debug builds only):

    val report = Python.getInstance()
        .getModule("netra_smoke").callAttr("run").toString()
    Log.i("NetraSmoke", report)

Probes every optional native dependency; the statutory core is the
floor — it must report ok in EVERY outcome (stdlib only, by design).
"""
import json


def _probe(name):
    try:
        __import__(name)
        return "ok"
    except Exception as e:
        return f"FAIL: {type(e).__name__}"


def run() -> str:
    report = {m: _probe(m) for m in ("cv2", "numpy", "PIL", "reportlab")}
    try:
        from netra_core.rules.usp import evaluate_usp
        r = evaluate_usp(50, 200, "g", declared="0.25", declared_unit="g")
        report["statutory_core"] = "ok" if r.compliant else "FAIL: math"
    except Exception as e:
        report["statutory_core"] = f"FAIL: {type(e).__name__}: {e}"
    try:
        from netra_core.bridge import chaquopy_api      # noqa: F401
        report["bridge"] = "ok"
    except Exception as e:
        report["bridge"] = f"FAIL: {type(e).__name__}"
    return json.dumps(report)
