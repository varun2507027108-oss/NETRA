"""Synthetic YOLO training corpus for package ROI detection (s2 model round).

Generates randomized 'photographed' packages with YOLO-format annotations
for the contract's ROI classes:

    0 PACKAGE   the package silhouette
    1 PDP       principal display panel (brand/product block, front face)
    2 PRICE     printed MRP region (front face)
    3 BARCODE   stripe block (front face, ~70% of images)
    4 BOP       back-of-pack declaration block (back-face images)

Domain randomization: noise, gradients, perspective warps, blur. Per-ANNOTATION_SPEC.md, PRICE is printed MRP only — never a shelf tag. Deterministic per-seed: the corpus is reproducible byte-for-byte (validated by tests/test_yolo_dataset.py) and re-identical on Colab.

This is SYNTHETIC PRETRAINING: it boots the ROI lane with zero field data. Real photographs (core/fixtures) fine-tune later — same images+labels layout, same data.yaml.

Run:  python scripts/make_yolo_dataset.py [--n 400] [--val 80] [--out core/yolo_ds]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CLASSES = ("PACKAGE", "PDP", "PRICE", "BARCODE", "BOP")
IMG = 640

_WORDS = ("Fresh Milk", "Noodle Pack", "Biscuit", "Tea", "Coffee",
          "Masala", "Choco", "Snack", "Juice", "Atta", "Detergent",
          "Shampoo", "Soap", "Oil", "Spice Mix", "Namkeen")
_BRANDS = ("TastyFoods", "GoldenCrop", "PureLife", "SunriseCo", "Veda",
           "FreshFarm", "MetroMart", "DailyPlus")
_PRICE_LINES = ("MRP Rs 50.00", "MRP 99.00", "incl of all taxes",
                "Unit Price 0.25", "M.R.P. Rs. 140.00")
_BACK_LINES = ("Mfd by Tasty Foods", "Plot 21 Goa 403001", "Net Qty 200 g",
               "Consumer Care 1800-123-4567", "care@tasty.in", "MFG 03/2026")


def _noise(rng_np, shape, base, spread):
    return np.clip(rng_np.normal(base, spread, shape), 0, 255).astype(np.uint8)


def _degrade(rng_np, frame):
    if rng_np.random() < 0.30:                      # perspective
        h, w = frame.shape[:2]
        k = int(w * 0.04)
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[k, k], [w - k, int(k * 0.4)],
                          [w - int(k * 1.5), h - int(k * 0.6)],
                          [int(k * 0.7), h - k]])
        fill = int(np.clip(rng_np.normal(90, 20), 0, 255))
        frame = cv2.warpPerspective(
            frame, cv2.getPerspectiveTransform(src, dst), (w, h),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(fill, fill, fill))
    if rng_np.random() < 0.35:                      # brightness ramp
        ramp = rng_np.uniform(-40, 0) * np.linspace(1, 0, frame.shape[0])[:, None, None]
        frame = np.clip(frame.astype(np.float64) + ramp, 0, 255).astype(np.uint8)
    if rng_np.random() < 0.20:                      # blur
        frame = cv2.GaussianBlur(frame, (0, 0), rng_np.uniform(0.6, 1.4))
    return frame


def _text_block(rng_py, frame, box, pool, size_range):
    x, y, w, h = box
    n = rng_py.randint(2, 4)
    step = h // (n + 1)
    for i in range(n):
        size = rng_py.randint(*size_range)
        cv2.putText(frame, rng_py.choice(pool), (x + 8, y + step * (i + 1)),
                    cv2.FONT_HERSHEY_SIMPLEX, size / 30.0, (30, 30, 30),
                    max(1, size // 12), cv2.LINE_AA)


def _barcode(rng_py, frame, box):
    x, y, w, h = box
    frame[y:y + h, x:x + w] = 245
    bar = rng_py.choice((3, 4, 5))
    for i, bx in enumerate(range(x + 8, x + w - 8 - bar, 2 * bar)):
        if i % 2 == 0:
            frame[y + 6:y + h - 6, bx:bx + bar] = 25


def gen_image(rng_py, rng_np, front: bool):
    """-> (frame, [(class_id, x, y, w, h), ...]) absolute pixels."""
    frame = _noise(rng_np, (IMG, IMG, 3), rng_py.uniform(70, 120), 8)
    pw, ph = rng_py.randint(300, 560), rng_py.randint(360, 580)
    x0 = rng_py.randint(30, IMG - 30 - pw)
    y0 = rng_py.randint(30, IMG - 30 - ph)
    frame[y0:y0 + ph, x0:x0 + pw] = _noise(
        rng_np, (ph, pw, 3), rng_py.uniform(205, 238), 6)
    labels = [(0, x0, y0, pw, ph)]                       # PACKAGE

    if front:
        pdp = (x0 + int(pw * 0.08), y0 + int(ph * 0.05),
               int(pw * 0.84), int(ph * 0.42))
        price = (x0 + int(pw * 0.10), y0 + int(ph * 0.55),
                 int(pw * 0.70), int(ph * 0.16))
        labels += [(1, *pdp), (2, *price)]
        _text_block(rng_py, frame, pdp, _BRANDS + _WORDS, (18, 34))
        _text_block(rng_py, frame, price, _PRICE_LINES, (16, 26))
        if rng_py.random() < 0.70:
            bw, bh = rng_py.randint(90, 150), rng_py.randint(50, 80)
            bcode = (x0 + pw - bw - int(pw * 0.05),
                     y0 + ph - bh - int(ph * 0.04), bw, bh)
            _barcode(rng_py, frame, bcode)
            labels.append((3, *bcode))
    else:                                                # back face
        bop = (x0 + int(pw * 0.10), y0 + int(ph * 0.15),
               int(pw * 0.80), int(ph * 0.65))
        labels.append((4, *bop))
        _text_block(rng_py, frame, bop, _BACK_LINES, (14, 24))

    return _degrade(rng_np, frame), labels


def _yolo_line(cid, x, y, w, h):
    cx, cy = (x + w / 2) / IMG, (y + h / 2) / IMG
    return f"{cid} {cx:.6f} {cy:.6f} {w / IMG:.6f} {h / IMG:.6f}"


def generate(out_dir: Path, n: int, val: int, seed: int) -> dict:
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    stats = {"train": 0, "val": 0, "by_class": {c: 0 for c in CLASSES}}
    for i in range(n):
        rng_py = random.Random(seed + i)
        rng_np = np.random.default_rng(seed + i)
        frame, labels = gen_image(rng_py, rng_np, front=(i % 2 == 0))
        split = "val" if i < val else "train"
        stem = f"pkg_{i:04d}"
        cv2.imwrite(str(out_dir / "images" / split / f"{stem}.jpg"), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        (out_dir / "labels" / split / f"{stem}.txt").write_text(
            "\n".join(_yolo_line(*l) for l in labels), encoding="utf-8")
        stats[split] += 1
        for cid, *_ in labels:
            stats["by_class"][CLASSES[cid]] += 1
    (out_dir / "data.yaml").write_text(
        f"path: {out_dir.resolve().as_posix()}\n"
        f"train: images/train\nval: images/val\n"
        f"names:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)),
        encoding="utf-8")
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--val", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20260906)
    ap.add_argument("--out", default=str(ROOT / "yolo_ds"))
    a = ap.parse_args()
    stats = generate(Path(a.out), a.n, a.val, a.seed)
    print(f"dataset -> {a.out}")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
