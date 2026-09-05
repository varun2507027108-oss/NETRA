import math

import cv2
import numpy as np
import pytest

pytest.importorskip("cv2")

from netra_core.context import BBox, OCRToken, PipelineContext   # noqa: E402
from netra_core.stages import s3_calibration, s5_field_extract   # noqa: E402
from netra_core.stages.s3_calibration import (                   # noqa: E402
    compute_pda, cylindrical_maps, estimate_cylinder_extent, run,
)
from netra_core.vision import aruco                              # noqa: E402

MARKER_MM = 40.0


def make_label_frame(marker_px=200, canvas=(640, 480)):
    """White canvas with a centred ArUco marker. -> (frame, marker_tl)."""
    W, H = canvas
    marker = aruco.generate_image(0, marker_px)
    frame = np.full((H, W, 3), 250, np.uint8)
    tl = ((W - marker_px) // 2, (H - marker_px) // 2)
    frame[tl[1]:tl[1] + marker_px,
          tl[0]:tl[0] + marker_px] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    return frame, tl


def _perspective_warp(frame, src_quad, dst_quad):
    M = cv2.getPerspectiveTransform(np.float32(src_quad), np.float32(dst_quad))
    return cv2.warpPerspective(frame, M, (frame.shape[1], frame.shape[0]))


# ------------------------------------------------------------- scale recovery
def test_scale_recovery_frontoparallel():
    frame, _ = make_label_frame(marker_px=200)
    ctx = PipelineContext()
    rep = run(ctx, frame)
    assert rep.ok and rep.mm_per_px is not None
    assert rep.mm_per_px == pytest.approx(MARKER_MM / 200.0, rel=0.01)
    # rectification preserves the marker's on-sensor scale by construction
    again = aruco.detect_markers(cv2.cvtColor(rep.frame, cv2.COLOR_BGR2GRAY))
    assert again
    side = float(np.linalg.norm(again[0][0][0] - again[0][0][1]))
    assert side == pytest.approx(200.0, abs=6.0)


def test_scale_recovery_under_perspective():
    frame, (x, y) = make_label_frame(marker_px=200)
    src = [[x, y], [x + 200, y], [x + 200, y + 200], [x, y + 200]]
    dst = [[x, y], [x + 160, y + 10], [x + 180, y + 190], [x + 20, y + 200]]
    ctx = PipelineContext()
    rep = run(ctx, _perspective_warp(frame, src, dst))
    assert rep.ok
    assert rep.mm_per_px == pytest.approx(0.2, rel=0.16)


def test_rectification_restores_square():
    frame, (x, y) = make_label_frame(marker_px=200)
    src = [[x, y], [x + 200, y], [x + 200, y + 200], [x, y + 200]]
    dst = [[x, y], [x + 160, y + 10], [x + 180, y + 190], [x + 20, y + 200]]
    ctx = PipelineContext()
    rep = run(ctx, _perspective_warp(frame, src, dst))
    again = aruco.detect_markers(cv2.cvtColor(rep.frame, cv2.COLOR_BGR2GRAY))
    assert again
    quad = again[0][0]
    sides = [float(np.linalg.norm(quad[i] - quad[(i + 1) % 4])) for i in range(4)]
    assert max(sides) / min(sides) < 1.05


def test_solvepnp_scale_with_known_intrinsics():
    frame, _ = make_label_frame(marker_px=200)
    K = s3_calibration._camera_matrix(800.0, frame.shape)
    markers = aruco.detect_markers(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    out = s3_calibration._solvepnp(markers[0][0], MARKER_MM, K)
    assert out is not None
    mm_per_px, tilt = out
    assert mm_per_px == pytest.approx(0.2, rel=0.03)
    assert tilt < 5.0


# ------------------------------------------------------------- metric heights
def test_rectified_frame_drives_font_heights():
    frame, _ = make_label_frame(marker_px=200)
    ctx = PipelineContext()
    run(ctx, frame)
    ctx.tokens = [OCRToken("Net Quantity: 70 g", BBox(50, 50, 220, 25), 0.9)]
    s5_field_extract.run(ctx)
    assert ctx.font_heights["net_qty"] == pytest.approx(5.0, abs=0.06)


# -------------------------------------------------------------------- cylinder
def test_cylindrical_maps_equal_arc_spacing():
    maps = cylindrical_maps(np.eye(3), 640, 200, centre_px=320.0, radius_px=150.0)
    assert maps is not None
    map_x, _ = map_y = maps
    centre = map_x.shape[1] // 2
    assert float(map_x[100, centre]) == pytest.approx(320.0, abs=0.5)
    for deg in (30.0, 60.0):
        col = int(centre + 150.0 * math.radians(deg))
        assert float(map_x[100, col]) == pytest.approx(
            320.0 + 150.0 * math.sin(math.radians(deg)), abs=0.5)


def test_estimate_cylinder_extent():
    gray = np.full((300, 400), 200, np.uint8)
    gray[:, 100:105] = 40
    gray[:, 295:300] = 40
    ext = estimate_cylinder_extent(gray)
    assert ext is not None
    left, right = ext
    assert left == pytest.approx(102, abs=4)
    assert right == pytest.approx(297, abs=4)


# ------------------------------------------------------------------------- PDA
def test_compute_pda_shapes():
    assert compute_pda("rectangular", height_cm=10, width_cm=6)[0] == 60.0
    pda, tag = compute_pda("cylindrical", height_cm=10, diameter_cm=6)
    assert pda == pytest.approx(0.40 * 10 * math.pi * 6)
    assert tag == "inspector-dims"
    pda, tag = compute_pda("cylindrical", height_cm=10, image_diameter_mm=60.0)
    assert pda == pytest.approx(0.40 * 10 * math.pi * 6)
    assert tag == "aruco-cylindrical"
    assert compute_pda("other", total_surface_cm2=500)[0] == 200.0
    assert compute_pda("pouch", height_cm=12, width_cm=8)[0] == 96.0
    assert compute_pda("cylindrical") == (None, "")


# ------------------------------------------------------------------- stage UX
def test_stage_retry_prompt_without_fiducial():
    frame = np.full((480, 640, 3), 250, np.uint8)
    cv2.rectangle(frame, (200, 200), (280, 260), 30, -1)   # blob, not a marker
    ctx = PipelineContext()
    rep = run(ctx, frame)
    assert not rep.ok and rep.mm_per_px is None
    assert any("fiducial" in p.lower() for p in ctx.quality["prompts"])


def test_stage_degraded_ok_with_dims_only():
    frame = np.full((480, 640, 3), 250, np.uint8)
    ctx = PipelineContext(shape_hint="rectangular")
    rep = run(ctx, frame, options={"package_height_cm": 10,
                                   "package_width_cm": 6})
    assert rep.ok and rep.mm_per_px is None
    assert rep.pda_cm2 == 60.0 and rep.pda_method == "inspector-dims"
    assert rep.frame.shape == frame.shape
    assert ctx.pda_cm2 == 60.0


def test_stage_full_calibration_sets_ctx():
    frame, _ = make_label_frame(marker_px=200)
    ctx = PipelineContext(shape_hint="rectangular")
    rep = run(ctx, frame, options={"package_height_cm": 10, "package_width_cm": 6,
                                   "blown": True})
    assert rep.ok
    assert ctx.mm_per_px == pytest.approx(0.2, rel=0.01)
    assert ctx.pda_cm2 == 60.0
    assert ctx.blown_or_molded is True
    assert ctx.pda_method == "inspector-dims"


def test_bbox_to_source_round_trip():
    frame, _ = make_label_frame(marker_px=200)      # marker centred at (320, 240)
    ctx = PipelineContext()
    rep = run(ctx, frame)
    h, w = rep.map_x.shape[:2]
    assert rep.map_x[h // 2, w // 2] == pytest.approx(320.0, abs=6.0)
    assert rep.map_y[h // 2, w // 2] == pytest.approx(240.0, abs=6.0)
