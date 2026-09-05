"""Deterministic package-geometry primitives (Stage 2 engine, no model).

Classical OpenCV only. Every function ADDS a constraint when confident
and returns None when not — on cluttered scenes Stage 2 degrades to a
no-op and the pipeline behaves exactly as it did before this stage
existed (never worse than status quo).
"""
from __future__ import annotations

import cv2
import numpy as np

from ..config import (BARCODE_MIN_ASPECT, BARCODE_MIN_COL_CV,
                      BARCODE_MIN_EDGE_DENSITY, PKG_BORDER_TOUCH_MAX,
                      PKG_MAX_AREA_FRAC, PKG_MIN_AREA_FRAC,
                      SHAPE_SAGITTA_FRAC)
from ..context import BBox

# Synthetic-tuned: 25x25 bridges 14px synthetic dark seam gaps in tests.
# A larger close kernel risks bridging the package silhouette to adjacent
# clutter on real shelf photos. Expect to revisit / calibrate against real fixtures.
_CLOSE_KERNEL = np.ones((25, 25), np.uint8)


def _touches_borders(x, y, w, h, W, H, tol: int = 2) -> int:
    return (int(x <= tol) + int(y <= tol)
            + int(x + w >= W - tol) + int(y + h >= H - tol))


def package_region(gray):
    """Dominant package silhouette (Otsu, both polarities, morphology).

    -> {"bbox": BBox, "contour": ndarray, "conf": float} | None.
    conf = rect fill x area-fraction confidence — a heuristic, not a
    probability. The package may be brighter OR darker than its
    background, so both Otsu polarities are tried and the more plausible
    silhouette wins. Candidates touching > PKG_BORDER_TOUCH_MAX frame
    borders are rejected (that is the background ring, not the package);
    so are candidates outside [MIN, MAX] area fraction.
    """
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thr = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    H, W = gray.shape[:2]
    best = None
    for mask in (thr, cv2.bitwise_not(thr)):
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _CLOSE_KERNEL)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        c = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(c))
        frac = area / float(W * H)
        if not (PKG_MIN_AREA_FRAC <= frac <= PKG_MAX_AREA_FRAC):
            continue
        x, y, w, h = cv2.boundingRect(c)
        if _touches_borders(x, y, w, h, W, H) > PKG_BORDER_TOUCH_MAX:
            continue
        rect_fill = area / float(max(1, w * h))
        conf = min(1.0, rect_fill * min(1.0, frac / 0.30))
        if best is None or conf > best["conf"]:
            best = {"bbox": BBox(int(x), int(y), int(w), int(h)),
                    "contour": c, "conf": round(conf, 3)}
    return best


def top_edge_curvature(contour, bbox):
    """Sagitta of the silhouette's top edge / bbox width.

    A curved top (can/jar seen slightly from above) exceeds ~0.04; flat
    cartons ~0. -> float | None (None when the outline is unusable)."""
    mask = np.zeros((bbox.h, bbox.w), np.uint8)
    shifted = contour - np.array([[bbox.x, bbox.y]], dtype=np.int32)
    cv2.drawContours(mask, [shifted], -1, 255, 1)
    col_any = mask.any(axis=0)
    if int(np.count_nonzero(col_any)) < int(bbox.w * 0.5):
        return None
    profile = mask.argmax(axis=0).astype(np.float64)
    prof = profile[np.where(col_any)[0]]
    if len(prof) < 8:
        return None
    xs = np.linspace(0.0, 1.0, len(prof))
    chord = prof[0] + (prof[-1] - prof[0]) * xs
    sag = float(np.max(chord - prof))
    return sag / float(max(1, bbox.w))


def seam_lines(gray, bbox):
    """Pouch seal seams: strong near-horizontal segments in the top and
    bottom 20% bands of the package. -> (top_found, bottom_found)."""
    x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
    edges = cv2.Canny(gray, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180.0, threshold=60,
                            minLineLength=int(w * 0.55), maxLineGap=8)
    top = bottom = False
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            if abs(int(y2) - int(y1)) > max(2, int(h * 0.02)):
                continue
            yc = (y1 + y2) / 2.0
            if y + 0.05 * h <= yc <= y + 0.25 * h:
                top = True
            elif y + 0.75 * h <= yc <= y + 0.95 * h:
                bottom = True
    return top, bottom


def top_width_ratio(contour, bbox):
    """Occupied width of the silhouette's top 12% band / bbox width
    (bottle necks are narrow). -> float | None."""
    mask = np.zeros((bbox.h, bbox.w), np.uint8)
    shifted = contour - np.array([[bbox.x, bbox.y]], dtype=np.int32)
    cv2.drawContours(mask, [shifted], -1, 255, -1)
    band = mask[:max(2, int(bbox.h * 0.12)), :]
    cols = band.any(axis=0)
    if not cols.any():
        return None
    best = cur = 0
    for c in cols:
        cur = cur + 1 if c else 0
        best = max(best, cur)
    return best / float(max(1, bbox.w))


def suggest_shape(gray, pkg):
    """Distinctive-shape suggestion from silhouette analysis.

    -> (shape, conf). Only DISTINCTIVE shapes are ever suggested
    (cylindrical / pouch / bottle); rectangular boxes are the null
    default, so a miss is an omission — never a wrong formula. The
    suggestion fills ctx.shape_detected for the report UI; the
    inspector's shape_hint stays authoritative for Rule 7(4).

    Order matters: bottle (narrow-top) must be checked BEFORE cylindrical
    (top-edge curvature). On a bottle, the top-edge profile is stepped:
    [shoulder, ..., neck-top, ..., shoulder]. The chord-minus-profile
    sagitta measures the shoulder height (e.g. 120px -> ~0.40 curvature),
    which would falsely trigger "cylindrical" before the bottle check is
    ever reached. Testing narrow-top first prevents this confound and
    cannot misfire on cylinders because a cylinder's top band spans the full
    silhouette width (ratio ≈ 1.0, never <= 0.5).
    """
    bbox, contour = pkg["bbox"], pkg["contour"]
    ratio = top_width_ratio(contour, bbox)
    if ratio is not None and ratio <= 0.5:
        return "bottle", 0.55
    curv = top_edge_curvature(contour, bbox)
    if curv is not None and curv >= SHAPE_SAGITTA_FRAC:
        return "cylindrical", round(min(1.0, curv * 6.0), 3)
    top, bottom = seam_lines(gray, bbox)
    if top and bottom:
        return "pouch", 0.6
    return "", 0.0


def barcode_region(gray, search_bbox=None):
    """1D barcode (EAN/UPC-style) localization — dense vertical-edge
    stripes. Sobel-X -> Otsu edge mask -> horizontal close (bridges the
    bars into one blob) -> wide candidates verified by in-box edge
    density AND column-profile periodicity (uniform noise has a flat
    column profile; bar stripes alternate strongly).

    -> {"bbox": BBox, "conf": float} | None; conf = in-box vertical-edge
    density on the PRE-close mask (not inflated by morphology).
    """
    x0 = y0 = 0
    roi = gray
    if search_bbox is not None:
        x0, y0 = search_bbox.x, search_bbox.y
        roi = gray[y0:y0 + search_bbox.h, x0:x0 + search_bbox.w]
        if roi.size == 0:
            return None
    gx = cv2.Sobel(roi, cv2.CV_32F, 1, 0, ksize=3)
    mag = np.abs(gx)
    peak = float(mag.max()) if mag.size else 0.0
    if peak <= 0:
        return None
    mag8 = (mag * (255.0 / peak)).astype(np.uint8)
    _, edges = cv2.threshold(mag8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3)))
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < 40 or h < 15 or w / float(h) < BARCODE_MIN_ASPECT:
            continue
        boxe = edges[y:y + h, x:x + w]
        density = float(np.count_nonzero(boxe)) / float(boxe.size)
        if density < BARCODE_MIN_EDGE_DENSITY:
            continue
        colprof = boxe.sum(axis=0).astype(np.float64)
        mean = colprof.mean()
        cv = float(colprof.std() / mean) if mean > 1e-6 else 0.0
        if cv < BARCODE_MIN_COL_CV:
            continue            # uniform edge noise, not bar stripes
        cand = {"bbox": BBox(x0 + int(x), y0 + int(y), int(w), int(h)),
                "conf": round(density, 3)}
        if best is None or cand["conf"] > best["conf"]:
            best = cand
    return best
