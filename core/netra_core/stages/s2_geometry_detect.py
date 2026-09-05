"""Stage 2 — packaging geometry & label detection (deterministic engine).

Spec role: shape segmentation + four ROIs (PDP/BOP/Price/Barcode) via
YOLO26n on-device (~39 ms). The CURRENT engine is deterministic OpenCV
— no model, no training data — delivering the subset achievable
reliably today:

  - package silhouette ROI and a crop of union(package, ADJACENT ArUco
    fiducial) + margin: OCR runs on the package, the calibration card
    survives the crop, background tokens disappear. All downstream
    bboxes are offset back to submitted-image space after Stage 5
    (contract section 5 preserved).
  - shape suggestion (cylindrical / pouch / bottle) from silhouette
    analysis — ctx.shape_detected only; the inspector's shape_hint
    stays authoritative for Rule 7(4) formulas; boxes are never
    suggested (null default).
  - GS1 barcode localization (vertical-edge stripes) — the one spec ROI
    achievable deterministically. PDP/BOP/Price ROIs land with the
    YOLO provider once fixture data exists (register a provider under
    the same run() surface; the pipeline and contract do not change).

Design law: the stage never makes things worse. Cluttered scene ->
no ROI, no crop, no suggestion; the pipeline behaves exactly as before.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from ..config import PKG_CROP_MARGIN_FRAC, PKG_CROP_MAX_AREA_FRAC
from ..context import BBox, PipelineContext
from ..vision import aruco, geometry

ROI_PACKAGE = "PACKAGE"
ROI_BARCODE = "BARCODE"
_MARKER_ADJACENCE = 0.5   # fiducial joins the crop when within half a
                          # package dimension of the package bbox


@dataclass(frozen=True)
class GeometryReport:
    ok: bool
    detail: str
    crop: Optional[np.ndarray] = None
    origin: tuple = (0, 0)           # (x, y) of crop in submitted space
    package_roi: Optional[BBox] = None
    package_conf: float = 0.0
    shape_suggestion: str = ""
    barcode_roi: Optional[BBox] = None
    barcode_conf: float = 0.0


def _marker_bbox(corners):
    xs = corners[:, 0].astype(int)
    ys = corners[:, 1].astype(int)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def run(ctx: PipelineContext, frame_bgr, options=None) -> GeometryReport:
    t0 = time.perf_counter()
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape[:2]

    pkg = geometry.package_region(gray)
    markers = aruco.detect_markers(gray)
    rois, notes = [], []
    crop, origin = None, (0, 0)
    suggestion, _conf = "", 0.0
    barcode = None

    if pkg is not None:
        rois.append({"roi": ROI_PACKAGE, "bbox": pkg["bbox"],
                     "conf": pkg["conf"]})
        suggestion, _conf = geometry.suggest_shape(gray, pkg)
        barcode = geometry.barcode_region(gray, search_bbox=pkg["bbox"])
        if barcode is not None:
            rois.append({"roi": ROI_BARCODE, "bbox": barcode["bbox"],
                         "conf": barcode["conf"]})

        # crop region: package + margin, plus ADJACENT fiducials so the
        # calibration card survives the crop (distant cards are excluded
        # and noted — hold the card next to the package)
        b = pkg["bbox"]
        x0, y0, x1, y1 = b.x, b.y, b.x2, b.y2
        reach = _MARKER_ADJACENCE * max(b.w, b.h)
        for corners, _mid, _area in markers:
            mx0, my0, mx1, my1 = _marker_bbox(corners)
            dx = max(0, mx0 - x1, x0 - mx1)
            dy = max(0, my0 - y1, y0 - my1)
            if max(dx, dy) <= reach:
                x0, y0 = min(x0, mx0), min(y0, my0)
                x1, y1 = max(x1, mx1), max(y1, my1)
            else:
                notes.append("fiducial outside package crop — hold the "
                             "card adjacent to the package")
        mx = int(PKG_CROP_MARGIN_FRAC * (x1 - x0))
        my = int(PKG_CROP_MARGIN_FRAC * (y1 - y0))
        x0, y0 = max(0, x0 - mx), max(0, y0 - my)
        x1, y1 = min(W, x1 + mx), min(H, y1 + my)
        if (x1 - x0) * (y1 - y0) <= PKG_CROP_MAX_AREA_FRAC * W * H:
            crop = frame_bgr[y0:y1, x0:x1].copy()
            origin = (int(x0), int(y0))
            notes.append(f"package ROI conf {pkg['conf']:.2f}; "
                         f"crop {x1 - x0}x{y1 - y0}")
        else:
            notes.append("crop would cover the frame — keeping full frame")
        if suggestion:
            notes.append(f"shape suggestion {suggestion} ({_conf:.2f})")
        if barcode is not None:
            notes.append(f"barcode ROI conf {barcode['conf']:.2f}")
    else:
        notes.append("no confident package silhouette — full frame")

    ctx.rois = rois
    ctx.shape_detected = suggestion
    ctx.add_stage("s2_geometry_detect", True,
                  (time.perf_counter() - t0) * 1000.0)
    return GeometryReport(
        True, "; ".join(notes), crop, origin,
        pkg["bbox"] if pkg else None, pkg["conf"] if pkg else 0.0,
        suggestion,
        barcode["bbox"] if barcode else None,
        barcode["conf"] if barcode else 0.0)
