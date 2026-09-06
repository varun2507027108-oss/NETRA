"""Desktop reference for the vision-prepass A/B.

    .venv\\Scripts\\python scripts\\ab_prepass.py <image.jpg> [--shape pouch]
        [--dims 20x16] | [--cyl 10x6] | [--surface 500]

Runs Python s1 + s3 (the reference implementation) on the image and
prints JSON to compare number-for-number against the device's
vision_prepass output on the SAME bytes.

Expected agreement: mm_per_px within ~5% (planar scale is focal-invariant;
the residual is the known method difference — Python uses side/sqrt(area),
Kotlin the mean linear scale of H, plus BitmapFactory-vs-cv2 JPEG decode
differences). Laplacian/glare agree DIRECTIONALLY (both above/below the
threshold) — decoder differences of a few percent are normal.
"""
import argparse
import json

import cv2
import numpy as np

from netra_core.bridge.schema import _parse_options
from netra_core.context import PipelineContext
from netra_core.stages import s1_frame_quality, s3_calibration


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--shape", default="rectangular")
    ap.add_argument("--dims", help="height_cm x width_cm (flat)")
    ap.add_argument("--cyl", help="height_cm x diameter_cm")
    ap.add_argument("--surface", type=float)
    a = ap.parse_args()

    raw = open(a.image, "rb").read()
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("undecodable image")
        return 2

    options = {}
    if a.dims:
        h, w = a.dims.lower().split("x")
        options = {"package_height_cm": float(h), "package_width_cm": float(w)}
    elif a.cyl:
        h, d = a.cyl.lower().split("x")
        options = {"package_height_cm": float(h),
                   "package_diameter_cm": float(d)}
    elif a.surface:
        options = {"total_surface_cm2": a.surface}
    opts, _err = _parse_options(options)

    ctx = PipelineContext(shape_hint=a.shape)
    q = s1_frame_quality.run(ctx, img)
    calib = s3_calibration.run(ctx, img, options=opts)
    print(json.dumps({
        "quality": ctx.quality,
        "geometry": {"mm_per_px": ctx.mm_per_px, "pda_cm2": ctx.pda_cm2,
                     "pda_method": ctx.pda_method or None,
                     "detail": calib.detail},
        "reference": {"laplacian_var": q.laplacian_var,
                      "glare_pct": q.glare_pct},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
