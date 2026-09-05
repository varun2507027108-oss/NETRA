"""Stage 3 — metric scale calibration & surface unwarping (~15 ms budget).

Recovers the pixel-to-millimetre scale from an ArUco fiducial card held
flat against the package, rectifies perspective, flattens cylindrical
surfaces, and computes the Principal Display Area per Rule 7(4).

Calibration paths:
- aruco-homography (default, desktop, NO camera intrinsics): the marker's
  4 corners define a planar homography from marker-plane millimetres to
  pixels; the rectified output image IS that plane at a uniform, exactly
  known mm/px. Planar scale is focal-length invariant — which is why this
  works without intrinsics.
- aruco-solvepnp (Android, real intrinsics via options.camera_focal_px):
  cv2.solvePnP yields pose; mm/px = depth / focal at the marker centre.
  Cross-checks the homography scale and reports tilt.

PDA sources (Rule 7(4)): inspector dimensions (height/width/diameter/
total surface) or the image-derived cylinder diameter (silhouette
half-width x mm/px). rectangular = H x W; cylindrical/bottle =
0.40 x H x pi x D; pouch = flat face (H x W); blister/other = 40% of
total surface.

Coordinate spaces: OCR and font measurement run on the corrected frame
(uniform mm/px); evidence bboxes are mapped BACK to submitted-image pixel
space by exact corner lookup in the remap tables (contract section 5).
All geometric corrections are expressed as cv2.remap maps so back-mapping
is a lookup, never an inversion.

Failure semantics:
- no fiducial AND no dimensions -> not ok -> RETRY with an inspector
  prompt (parallel to the Stage 1 glare UX);
- no fiducial but dimensions given -> ok, degraded: Rule 7 checks NA;
- PDA outside sanity bounds -> treated as not computed.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from ..config import (ARUCO_MARKER_MM, CYL_MAX_RADIUS_MM, CYL_MIN_RADIUS_PX,
                      CYL_THETA_LIMIT_DEG, FOCAL_RATIO_DEFAULT, MAX_RECT_SCALE,
                      PDA_SANITY_CM2)
from ..context import BBox, PipelineContext
from ..rules.table1_fonts import (pda_cylindrical_cm2, pda_other_cm2,
                                  pda_rectangular_cm2)
from ..vision import aruco

FLAT_SHAPES = ("rectangular", "pouch")
ROUND_SHAPES = ("cylindrical", "bottle")


@dataclass(frozen=True)
class CalibrationReport:
    ok: bool
    mm_per_px: Optional[float]
    pda_cm2: Optional[float]
    pda_method: str
    detail: str
    frame: Optional[np.ndarray] = None     # corrected frame for Stage 4
    map_x: Optional[np.ndarray] = None     # output px -> submitted px
    map_y: Optional[np.ndarray] = None
    marker_id: Optional[int] = None
    tilt_deg: Optional[float] = None

    def bbox_to_source(self, bbox: BBox) -> BBox:
        """Output-space bbox -> submitted-image bbox (axis-aligned box of
        the remapped corners; exact per-corner, approximate as a box)."""
        if self.map_x is None or bbox is None:
            return bbox
        h, w = self.map_x.shape[:2]
        xs, ys = [], []
        for px, py in ((bbox.x, bbox.y), (bbox.x2 - 1, bbox.y),
                       (bbox.x, bbox.y2 - 1), (bbox.x2 - 1, bbox.y2 - 1)):
            px = int(min(max(px, 0), w - 1))
            py = int(min(max(py, 0), h - 1))
            xs.append(float(self.map_x[py, px]))
            ys.append(float(self.map_y[py, px]))
        x0, y0 = min(xs), min(ys)
        return BBox(int(round(x0)), int(round(y0)),
                    int(round(max(xs) - x0)), int(round(max(ys) - y0)))


# ------------------------------------------------------------ planar rectify
def _marker_object_mm(side_mm: float) -> np.ndarray:
    """Marker corners in its own plane (X right, Y down), matching OpenCV's
    detected corner order TL, TR, BR, BL."""
    s = side_mm / 2.0
    return np.array([[-s, -s], [s, -s], [s, s], [-s, s]], dtype=np.float32)


def _plane_transform(corners_px, side_mm: float, src_shape):
    """Composite output->source transform for planar rectification.

    -> (C, out_w, out_h, mm_per_px): C maps homogeneous output pixels to
    source pixels; output scale is uniform mm_per_px; the output extent
    covers the whole source image. Raises ValueError on degenerate or
    too-oblique geometry.
    """
    h, w = src_shape[:2]
    obj = _marker_object_mm(side_mm)
    H, _ = cv2.findHomography(obj, np.asarray(corners_px, np.float32), 0)
    if H is None:
        raise ValueError("degenerate marker geometry")
    area_px = cv2.contourArea(np.asarray(corners_px, np.float32))
    if area_px < 25.0:
        raise ValueError("marker too small to calibrate")
    mm_per_px = float(side_mm) / math.sqrt(area_px)

    src_corners = np.array([[[0, 0]], [[w, 0]], [[w, h]], [[0, h]]],
                           dtype=np.float32)
    plane_mm = cv2.perspectiveTransform(
        src_corners, np.linalg.inv(H).astype(np.float32))
    out_pts = plane_mm.reshape(4, 2) / mm_per_px
    x0, y0 = out_pts.min(axis=0)
    x1, y1 = out_pts.max(axis=0)
    out_w = int(math.ceil(x1 - x0)) + 1
    out_h = int(math.ceil(y1 - y0)) + 1
    if out_w > MAX_RECT_SCALE * w or out_h > MAX_RECT_SCALE * h:
        raise ValueError("marker plane too oblique to rectify")

    scale = np.diag([mm_per_px, mm_per_px, 1.0])
    shift = np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], dtype=np.float64)
    C = H.astype(np.float64) @ scale @ shift
    return C, out_w, out_h, mm_per_px


def _maps_from_transform(C, out_w: int, out_h: int):
    """Output grid -> source pixel lookup tables for cv2.remap."""
    ux, uy = np.meshgrid(np.arange(out_w, dtype=np.float32),
                         np.arange(out_h, dtype=np.float32))
    pts = np.stack([ux, uy], axis=-1).reshape(-1, 1, 2)
    src = cv2.perspectiveTransform(pts, np.asarray(C, np.float32))
    return (src[:, :, 0].reshape(out_h, out_w).astype(np.float32),
            src[:, :, 1].reshape(out_h, out_w).astype(np.float32))


# ------------------------------------------------------------------ cylinder
def estimate_cylinder_extent(gray):
    """Silhouette heuristic: the two dominant vertical-edge columns in the
    central band. -> (left_x, right_x) | None."""
    h, w = gray.shape[:2]
    sob = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    energy = sob.sum(axis=0)
    lo, hi = int(0.15 * w), int(0.85 * w)
    if hi - lo < 20:
        return None
    seg = np.convolve(energy[lo:hi].astype(np.float64),
                      np.ones(5) / 5.0, mode="same")
    order = np.argsort(seg)[::-1]
    first = int(order[0])
    second = next((int(i) for i in order
                   if abs(int(i) - first) > 0.25 * (hi - lo)), None)
    if second is None:
        return None
    left, right = sorted((lo + first, lo + second))
    return left, right


def cylindrical_maps(C, plane_w: int, plane_h: int, centre_px: float,
                     radius_px: float):
    """Arc-length cylinder unwarp composed with the planar transform.

    Output column u (centred on the axis) covers arc angle theta = u / R;
    the plane coordinate sampled is x = centre + R*sin(theta) (orthographic
    cylinder model: silhouette half-width == R), then mapped to source
    pixels through C. Vertical stripes equally spaced on the cylinder
    become equally spaced in the output — true millimetre geometry for
    OCR and font measurement. -> (map_x, map_y) | None.
    """
    theta_lim = math.radians(CYL_THETA_LIMIT_DEG)
    span = radius_px * theta_lim
    out_w = int(2 * span)
    out_h = plane_h
    if out_w < 8 or radius_px <= 0:
        return None
    u = np.arange(out_w, dtype=np.float32) - out_w / 2.0
    x_plane = centre_px + radius_px * np.sin(u / radius_px)
    map_x_plane = np.tile(x_plane, (out_h, 1))
    map_y_plane = np.tile(np.arange(out_h, dtype=np.float32)[:, None],
                          (1, out_w))
    pts = np.stack([map_x_plane, map_y_plane], axis=-1).reshape(-1, 1, 2)
    src = cv2.perspectiveTransform(pts, np.asarray(C, np.float32))
    return (src[:, :, 0].reshape(out_h, out_w).astype(np.float32),
            src[:, :, 1].reshape(out_h, out_w).astype(np.float32))


# ---------------------------------------------------------------------- PDA
def compute_pda(shape, *, height_cm=None, width_cm=None, diameter_cm=None,
                total_surface_cm2=None, image_diameter_mm=None):
    """Rule 7(4) PDA from the best available source. -> (pda | None, tag)."""
    shape = (shape or "").lower()
    if shape in ROUND_SHAPES:
        if height_cm and diameter_cm:
            return pda_cylindrical_cm2(height_cm, diameter_cm), "inspector-dims"
        if height_cm and image_diameter_mm:
            return (pda_cylindrical_cm2(height_cm, image_diameter_mm / 10.0),
                    "aruco-cylindrical")
        return None, ""
    if shape in FLAT_SHAPES and height_cm and width_cm:
        return pda_rectangular_cm2(height_cm, width_cm), "inspector-dims"
    if total_surface_cm2:
        return pda_other_cm2(total_surface_cm2), "inspector-dims"
    if height_cm and width_cm:            # shape unknown, flat dims given
        return pda_rectangular_cm2(height_cm, width_cm), "inspector-dims"
    return None, ""


# --------------------------------------------------------------------- pose
def _camera_matrix(focal_px: float, shape):
    h, w = shape[:2]
    return np.array([[focal_px, 0, w / 2.0],
                     [0, focal_px, h / 2.0],
                     [0, 0, 1.0]], dtype=np.float64)


def _solvepnp(corners_px, side_mm: float, camera_matrix):
    """Pose from the marker. -> (mm_per_px, tilt_deg) | None. mm/px =
    depth / focal at the marker centre — focal-invariant for a planar
    target, so this is valid even with an approximate focal length."""
    obj3 = np.hstack([_marker_object_mm(side_mm),
                      np.zeros((4, 1), np.float32)]).astype(np.float32)
    res = cv2.solvePnP(obj3, np.asarray(corners_px, np.float32),
                       camera_matrix, None, flags=cv2.SOLVEPNP_IPPE)
    ok, rvec, tvec = res[0], res[1], res[2]
    if not ok:
        return None
    rot, _ = cv2.Rodrigues(rvec)
    normal = rot @ np.array([0.0, 0.0, 1.0])
    tilt = math.degrees(math.acos(min(1.0, abs(float(normal[2])))))
    depth, focal = float(tvec.reshape(-1)[2]), float(camera_matrix[0, 0])
    if depth <= 0 or focal <= 0:
        return None
    return depth / focal, tilt


def _opt_float(opts, key):
    v = opts.get(key)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------- stage
def run(ctx: PipelineContext, frame_bgr, options=None) -> CalibrationReport:
    """Calibrate scale, correct geometry, compute PDA; populate ctx."""
    t0 = time.perf_counter()
    opts = dict(options or {})
    ctx.blown_or_molded = bool(opts.get("blown"))

    marker_side_mm = float(opts.get("marker_side_mm") or ARUCO_MARKER_MM)
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    mm_per_px = None
    C = None
    out_w = out_h = 0
    map_x = map_y = None
    corrected = None
    marker_id = None
    tilt_deg = None
    notes = []

    markers = aruco.detect_markers(gray)
    if markers:
        corners, marker_id, _area = markers[0]
        try:
            C, out_w, out_h, mm_per_px = _plane_transform(
                corners, marker_side_mm, frame_bgr.shape)
            map_x, map_y = _maps_from_transform(C, out_w, out_h)
            corrected = cv2.remap(frame_bgr, map_x, map_y, cv2.INTER_LINEAR,
                                  cv2.BORDER_CONSTANT, borderValue=(245, 245, 245))
            ctx.mm_per_px = round(mm_per_px, 6)
            focal = opts.get("camera_focal_px") or \
                FOCAL_RATIO_DEFAULT * max(frame_bgr.shape[:2])
            pose = _solvepnp(corners, marker_side_mm,
                             _camera_matrix(float(focal), frame_bgr.shape))
            if pose is not None:
                pose_scale, tilt_deg = pose
                if abs(pose_scale - mm_per_px) / mm_per_px > 0.15:
                    notes.append(f"solvePnP scale disagrees by "
                                 f"{abs(pose_scale - mm_per_px) / mm_per_px:.0%}"
                                 f" — homography scale kept")
            notes.append(f"fiducial #{marker_id}: {mm_per_px:.4f} mm/px"
                         + (f", tilt {tilt_deg:.1f} deg"
                            if tilt_deg is not None else ""))
        except ValueError as e:
            notes.append(f"calibration rejected: {e}")

    # ---- cylindrical flattening (requires metric calibration) -----------
    image_diameter_mm = None
    shape = (ctx.shape_hint or "").lower()
    if mm_per_px is not None and C is not None:
        extent = None
        if opts.get("cylinder_left_px") is not None and \
                opts.get("cylinder_right_px") is not None:
            extent = (int(opts["cylinder_left_px"]),
                      int(opts["cylinder_right_px"]))
        elif shape in ROUND_SHAPES:
            extent = estimate_cylinder_extent(
                cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY))
        if extent is not None:
            left, right = extent
            radius_px = (right - left) / 2.0
            centre_px = (right + left) / 2.0
            radius_mm = radius_px * mm_per_px
            if CYL_MIN_RADIUS_PX <= radius_px <= CYL_MAX_RADIUS_MM / mm_per_px:
                cyl = cylindrical_maps(C, out_w, out_h, centre_px, radius_px)
                if cyl is not None:
                    map_x, map_y = cyl
                    corrected = cv2.remap(frame_bgr, map_x, map_y,
                                          cv2.INTER_LINEAR, cv2.BORDER_CONSTANT,
                                          borderValue=(245, 245, 245))
                    image_diameter_mm = 2.0 * radius_mm
                    notes.append(f"cylinder flattened: "
                                 f"D {image_diameter_mm:.0f} mm (image-derived)")

    # ---- PDA --------------------------------------------------------------
    pda, method = compute_pda(
        shape,
        height_cm=_opt_float(opts, "package_height_cm"),
        width_cm=_opt_float(opts, "package_width_cm"),
        diameter_cm=_opt_float(opts, "package_diameter_cm"),
        total_surface_cm2=_opt_float(opts, "total_surface_cm2"),
        image_diameter_mm=image_diameter_mm)
    if pda is not None and not (PDA_SANITY_CM2[0] <= pda <= PDA_SANITY_CM2[1]):
        notes.append(f"PDA {pda:.0f} cm² outside sanity range — ignored")
        pda, method = None, ""
    if pda is not None:
        ctx.pda_cm2 = round(float(pda), 2)
        ctx.pda_method = method

    # ---- outcome ------------------------------------------------------------
    if mm_per_px is None and pda is None:
        prompt = ("No ArUco fiducial in frame — hold the NETRA calibration "
                  "card flat against the package, or enter package dimensions")
        ctx.quality.setdefault("prompts", []).append(prompt)
        ctx.add_stage("s3_calibration", False, (time.perf_counter() - t0) * 1000.0)
        return CalibrationReport(False, None, None, "", prompt)

    if mm_per_px is None:
        notes.append("uncalibrated: Rule 7 font checks will report NA")
    report = CalibrationReport(
        ok=True,
        mm_per_px=ctx.mm_per_px,
        pda_cm2=ctx.pda_cm2,
        pda_method=ctx.pda_method,
        detail="; ".join(notes) or "calibrated",
        frame=corrected if corrected is not None else frame_bgr,
        map_x=map_x, map_y=map_y,
        marker_id=marker_id, tilt_deg=tilt_deg)
    ctx.add_stage("s3_calibration", True, (time.perf_counter() - t0) * 1000.0)
    return report
