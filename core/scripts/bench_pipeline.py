"""Per-stage latency benchmark vs the SIH stage budgets (deck evidence).

    .venv\\Scripts\\python scripts\\bench_pipeline.py --runs 25

Measures two paths:
  DEMO  — s4(dev-injection) -> s5 -> s6 over _DEMO_TOKENS: the statutory
          core's intrinsic cost (the sub-millisecond engine claims)
  PHOTO — s1 -> s2 -> s3 -> s4(tesseract) -> s5 -> s6 -> s7 on a
          synthetic photographed label (fiducial + printed text), when
          the tesseract binary is available: the realistic desktop number

Prints mean per-stage ms vs STAGE_BUDGET_MS (config) and totals. The
spec's 1.2–1.5 s end-to-end claim is judged against the PHOTO total,
with the honest note that ML Kit on-device replaces the tesseract tier
in production. Dossier writes go to a temp dir and are cleaned up.
"""
from __future__ import annotations

import argparse
import base64
import statistics
import tempfile
from pathlib import Path

import cv2
import numpy as np

from netra_core import paths
from netra_core.bridge.schema import scan_request_from_dict
from netra_core.config import STAGE_BUDGET_MS
from netra_core.ocr import tesseract_bridge
from netra_core.pipeline import run_demo_scan, run_scan
from netra_core.vision import aruco

PHOTO_STAGES = ("s1_frame_quality", "s2_geometry_detect", "s3_calibration",
                "s4_ocr", "s5_field_extract", "s6_metrology", "s7_dossier")
DEMO_STAGES = ("s4_ocr", "s5_field_extract", "s6_metrology")


def _photo_request():
    frame = np.full((1400, 1000, 3), 250, np.uint8)
    marker = aruco.generate_image(0, 200)
    frame[60:260, 60:260] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    for y, text in [
            (340, "Instant Masala Noodles"),
            (560, "Net Quantity: 70 g"),
            (700, "MRP Rs 50.00 (incl. of all taxes)"),
            (840, "MFG 03/2026"),
            (980, "Mfd. by: Tasty Foods Ltd.,"),
            (1090, "Plot 21, Goa 403001"),
            (1230, "Made in India")]:
        cv2.putText(frame, text, (320, y), cv2.FONT_HERSHEY_SIMPLEX, 1.5,
                    (25, 25, 25), 3, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    req, err = scan_request_from_dict({
        "image_b64": base64.b64encode(buf.tobytes()).decode("ascii"),
        "shape_hint": "rectangular",
        "options": {"package_height_cm": 14.0, "package_width_cm": 10.0}})
    assert err is None
    return req


def _table(title, rows, stages) -> float:
    print(f"\n{title}  ({len(rows)} runs)")
    print(f"{'stage':<20}{'budget_ms':>11}{'mean_ms':>10}")
    total = 0.0
    for s in stages:
        vals = [r["timings_ms"][s] for r in rows if s in r["timings_ms"]]
        if not vals:
            continue
        m = statistics.mean(vals)
        total += m
        budget = STAGE_BUDGET_MS.get(s)
        b = f"{budget:.1f}" if budget is not None else "-"
        flag = "  (over budget)" if budget is not None and m > budget else ""
        print(f"{s:<20}{b:>11}{m:>10.2f}{flag}")
    print(f"{'TOTAL':<20}{'':>11}{total:>10.2f}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=25)
    a = ap.parse_args()

    demo_rows = [run_demo_scan() for _ in range(a.runs)]
    _table("DEMO path (s4 dev-injection -> s5 -> s6)", demo_rows, DEMO_STAGES)

    if tesseract_bridge.available():
        tesseract_bridge.register()
        tmp = tempfile.TemporaryDirectory()
        paths.set_data_dir(Path(tmp.name))
        try:
            req = _photo_request()
            photo_rows = [run_scan(req) for _ in range(a.runs)]
        finally:
            paths.set_data_dir(None)
            try:
                tmp.cleanup()
            except OSError:
                pass
        total = _table("PHOTO path (s1 -> s2 -> s3 -> s4 tesseract -> "
                       "s5 -> s6 -> s7)", photo_rows, PHOTO_STAGES)
        print(f"\nend-to-end (desktop, tesseract tier): {total:.0f} ms"
              f"  — spec claim: 1200–1500 ms with on-device ML Kit")
        print("note: tesseract is the DESKTOP dev tier; production runs "
              "ML Kit on-device (sub-30 ms block OCR per the spec).")
    else:
        print("\nPHOTO path skipped — tesseract binary not available")
        print(tesseract_bridge.INSTALL_HINT)


if __name__ == "__main__":
    main()
