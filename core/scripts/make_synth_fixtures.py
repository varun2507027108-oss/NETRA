"""NETRA synthetic fixture generator — plumbing validation for the
golden-report machinery (NOT a substitute for real photographs).

Renders seven 'photographed' labels (ArUco fiducial + printed statutory
declarations, one controlled degradation per variant) plus a matching
labels_gt.json into core/fixtures/synth/, then (default) runs
make_fixtures.py over them.

Proves: file I/O -> s1 gate -> s2 crop -> s3 ArUco calibration ->
s4 Tesseract (line tokens) -> s5 extraction -> s6 engine -> golden
comparison -> report. Does NOT prove field accuracy on real packaging.
Real photos + gt belong in core/fixtures/labels/ — untouched here.

Expected first report: S01-S06 mostly ok; S07 (blur) should classify as
capture_retry — the s1 quality gate doing its job, not a failure.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from netra_core.vision import aruco

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT_DEFAULT = ROOT / "fixtures" / "synth"

FRAME_W, FRAME_H = 1300, 1600
PKG_X, PKG_Y, PKG_W, PKG_H = 200, 300, 800, 1000
MARKER_PX = 200                       # 40 mm at the 0.2 mm/px scene scale
MARKER_AT = (1030, 320)               # adjacent right: inside s2 crop reach
BG, FG = 70, 235
DIMS_CM = {"height": 20.0, "width": 16.0}   # 1000px*0.2, 800px*0.2

FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_X = PKG_X + 60
NAME_SCALE, BODY_SCALE, THICK = 1.1, 0.9, 2

# (field key | None = wrapped line, text, baseline y)
LINES = (
    ("product_name",  "Instant Masala Noodles",            450),
    ("net_qty",       "Net Quantity: 200 g",               610),
    ("mrp",           "MRP Rs 50.00 (incl. of all taxes)", 690),
    ("usp",           "Unit Sale Price Rs 0.25 / g",       770),
    ("mfg_date",      "MFG 03/2026",                       850),
    ("mfg_address",   "Mfd. by: Tasty Foods Ltd.,",        950),
    (None,            "Plot 21, Goa 403001",               986),
    ("origin",        "Made in India",                     1060),
    ("consumer_care", "Consumer Care: Tasty Foods,",       1150),
    (None,            "Mumbai 400050, Tel: 1800-123-4567", 1186),
    (None,            "care@tasty.in",                     1222),
)
BASE_FIELDS = {k: t for k, t, _ in LINES if k}

VARIANTS = (
    # key, field overrides (None = drop that block), expect_fail, degradation
    ("S01_clean", {}, [], "clean"),
    ("S02_gms", {"net_qty": "Net Quantity: 200 gms"},
     ["13", "6(1)(c)"], "clean"),
    ("S03_no_tax_phrase", {"mrp": "MRP Rs 50.00"}, ["6(1)(e)"], "clean"),
    ("S04_bad_usp", {"usp": "Unit Sale Price Rs 0.35 / g"},
     ["6(11)"], "noise"),
    ("S05_prc", {"origin": "Made in PRC"}, ["6(1)(aa)"], "perspective"),
    ("S06_multi", {"net_qty": "Net Quantity: 200 gms",
                   "origin": "Made in PRC"},
     ["13", "6(1)(c)", "6(1)(aa)"], "gradient"),
    ("S07_blur", {}, [], "blur"),        # compliant + blur -> capture_retry
)


def _base_frame(rng) -> np.ndarray:
    frame = np.clip(rng.normal(BG, 6, (FRAME_H, FRAME_W, 3)),
                    0, 255).astype(np.uint8)
    patch = np.clip(rng.normal(FG, 6, (PKG_H, PKG_W, 3)),
                    0, 255).astype(np.uint8)
    frame[PKG_Y:PKG_Y + PKG_H, PKG_X:PKG_X + PKG_W] = patch
    return frame                          # per-pixel noise also keeps the
                                           # s1 Laplacian gate comfortably
                                           # above 100 on clean variants


def _draw_lines(frame, draw_fields) -> None:
    skipping = False
    for key, default_text, y in LINES:
        if key is not None:
            content = draw_fields.get(key)
            skipping = content is None
            if skipping:
                continue
            text = content
        else:
            if skipping:
                continue
            text = default_text
        scale = NAME_SCALE if key == "product_name" else BODY_SCALE
        cv2.putText(frame, text, (TEXT_X, y), FONT, scale,
                    (30, 30, 30), THICK, cv2.LINE_AA)


def _degrade(frame, kind, rng) -> np.ndarray:
    if kind == "blur":
        return cv2.GaussianBlur(frame, (0, 0), 1.5)
    if kind == "noise":
        n = rng.normal(0, 10, frame.shape)
        return np.clip(frame.astype(np.float64) + n, 0, 255).astype(np.uint8)
    if kind == "perspective":
        h, w = frame.shape[:2]
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[25, 40], [w - 12, 8],
                          [w - 35, h - 18], [45, h - 8]])
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(frame, M, (w, h),
                                   borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=(55, 55, 55))
    if kind == "gradient":
        ramp = np.linspace(0.0, -28.0, frame.shape[0])[:, None, None]
        return np.clip(frame.astype(np.float64) + ramp,
                       0, 255).astype(np.uint8)
    return frame


def generate(out_dir: Path) -> dict:
    images = out_dir / "labels"
    images.mkdir(parents=True, exist_ok=True)
    gt = {}
    for i, (key, overrides, expect, kind) in enumerate(VARIANTS):
        rng = np.random.default_rng(1000 + i)
        frame = _base_frame(rng)
        draw_fields = {**BASE_FIELDS, **overrides}
        _draw_lines(frame, draw_fields)
        marker = aruco.generate_image(i, MARKER_PX)
        frame[MARKER_AT[1]:MARKER_AT[1] + MARKER_PX,
              MARKER_AT[0]:MARKER_AT[0] + MARKER_PX] = \
            cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        frame = _degrade(frame, kind, rng)
        cv2.imwrite(str(images / f"{key}.jpg"), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        gt[key] = {"shape": "rectangular", "dims_cm": DIMS_CM,
                   "fields": {k: v for k, v in draw_fields.items()
                              if v is not None},
                   "expect_fail": expect,
                   "notes": f"synthetic, degradation={kind}"}
    (out_dir / "labels_gt.json").write_text(
        json.dumps(gt, indent=2), encoding="utf-8")
    return gt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--no-run", action="store_true",
                    help="generate files only; skip the golden report")
    a = ap.parse_args()
    out_dir = Path(a.out)
    gt = generate(out_dir)
    print(f"generated {len(gt)} synthetic fixtures -> {out_dir}")
    print("NOTE: synthetic fixtures validate PLUMBING, not field accuracy;")
    print("      real photos + gt belong in core/fixtures/labels/")
    if a.no_run:
        return 0
    from netra_core.ocr import tesseract_bridge
    if not tesseract_bridge.available():
        print("\ntesseract binary unavailable — run the report later with:")
        print(f"  python scripts/make_fixtures.py "
              f"--gt {out_dir / 'labels_gt.json'} "
              f"--images {out_dir / 'labels'} "
              f"--report {out_dir / 'golden_report.json'}")
        return 0
    return subprocess.call([
        sys.executable, str(SCRIPTS / "make_fixtures.py"),
        "--gt", str(out_dir / "labels_gt.json"),
        "--images", str(out_dir / "labels"),
        "--report", str(out_dir / "golden_report.json"),
        "--report-only"])


if __name__ == "__main__":
    raise SystemExit(main())
