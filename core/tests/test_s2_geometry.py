import base64

import cv2
import numpy as np
import pytest

pytest.importorskip("cv2")

from netra_core.context import BBox, OCRToken, PipelineContext   # noqa: E402
from netra_core.stages import s2_geometry_detect, s4_ocr          # noqa: E402
from netra_core.vision import aruco, geometry                     # noqa: E402


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    from netra_core import paths
    from netra_core.persistence import queue_db
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    yield
    queue_db.reset()
    paths.set_data_dir(None)


def package_frame(rect=(150, 100, 400, 500), size=(900, 700),
                  bg=110, fg_base=220, noise=12, seed=3):
    """Bright noisy package on a darker plain background."""
    rng = np.random.default_rng(seed)
    W, H = size
    frame = np.full((H, W, 3), bg, np.uint8)
    x, y, w, h = rect
    patch = np.clip(rng.integers(fg_base - noise, fg_base + noise,
                                 (h, w, 3)), 0, 255).astype(np.uint8)
    frame[y:y + h, x:x + w] = patch
    return frame


def barcode_frame(size=(900, 700)):
    frame = package_frame(size=size)
    bx, by, bw, bh = 250, 450, 240, 90
    frame[by:by + bh, bx:bx + bw] = 245          # quiet zone
    bar = 3
    for i, x in enumerate(range(bx + 10, bx + bw - 10, 2 * bar)):
        if i % 2 == 0:
            frame[by + 5:by + bh - 5, x:x + bar] = 25
    return frame, BBox(bx, by, bw, bh)


def _iou(a, b):
    ix = max(0, min(a.x + a.w, b.x + b.w) - max(a.x, b.x))
    iy = max(0, min(a.y + a.h, b.y + b.h) - max(a.y, b.y))
    inter = ix * iy
    return inter / (a.w * a.h + b.w * b.h - inter)


def _tok(x, y, w, h, text, conf=0.97):
    return OCRToken(text=text, bbox=BBox(x, y, w, h), conf=conf,
                    engine="tesseract", lang="en")


# ------------------------------------------------------------- silhouette
def test_package_region_finds_bright_package():
    gray = cv2.cvtColor(package_frame(), cv2.COLOR_BGR2GRAY)
    pkg = geometry.package_region(gray)
    assert pkg is not None and pkg["conf"] > 0.5
    assert abs(pkg["bbox"].x - 150) <= 6 and abs(pkg["bbox"].y - 100) <= 6
    assert abs(pkg["bbox"].w - 400) <= 12 and abs(pkg["bbox"].h - 500) <= 12
    assert pkg["bbox"].w < 800            # the package, not the bg ring


def test_package_region_finds_dark_package():
    gray = cv2.cvtColor(package_frame(bg=220, fg_base=100),
                        cv2.COLOR_BGR2GRAY)
    pkg = geometry.package_region(gray)
    assert pkg is not None
    assert abs(pkg["bbox"].x - 150) <= 6


def test_package_region_none_on_uniform_noise():
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 255, (700, 900, 3), np.uint8)
    assert geometry.package_region(
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)) is None


# ----------------------------------------------------------------- barcode
def test_barcode_region_detects_stripes():
    frame, want = barcode_frame()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found = geometry.barcode_region(gray)
    assert found is not None and found["conf"] >= 0.28
    assert _iou(found["bbox"], want) >= 0.5


def test_barcode_region_none_on_plain_package():
    gray = cv2.cvtColor(package_frame(), cv2.COLOR_BGR2GRAY)
    assert geometry.barcode_region(gray) is None


def test_barcode_region_none_on_noise():
    rng = np.random.default_rng(2)
    frame = rng.integers(0, 200, (700, 900), np.uint8)
    assert geometry.barcode_region(frame) is None   # flat column profile


# ---------------------------------------------------------- shape signals
def test_shape_suggestion_cylindrical():
    frame = np.full((700, 900, 3), 110, np.uint8)
    x, y, w, h = 250, 150, 400, 480
    cv2.rectangle(frame, (x, y + 40), (x + w, y + h), (225,) * 3, -1)
    cv2.ellipse(frame, (x + w // 2, y + 40), (w // 2, 40), 0, 0, 360,
                (225,) * 3, -1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    pkg = geometry.package_region(gray)
    shape, conf = geometry.suggest_shape(gray, pkg)
    assert shape == "cylindrical" and conf > 0


def test_shape_suggestion_pouch():
    frame = package_frame()
    x, y, w, h = 150, 100, 400, 500
    cv2.rectangle(frame, (x, y + 30), (x + w, y + 44), (30,) * 3, -1)
    cv2.rectangle(frame, (x, y + h - 44), (x + w, y + h - 30), (30,) * 3, -1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    pkg = geometry.package_region(gray)
    assert geometry.suggest_shape(gray, pkg)[0] == "pouch"


def test_shape_suggestion_bottle():
    frame = np.full((700, 900, 3), 110, np.uint8)
    x, y, w, h = 300, 100, 300, 500
    cv2.rectangle(frame, (x, y + 120), (x + w, y + h), (225,) * 3, -1)
    cv2.rectangle(frame, (x + 100, y), (x + 200, y + 130), (225,) * 3, -1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    pkg = geometry.package_region(gray)
    assert geometry.suggest_shape(gray, pkg)[0] == "bottle"


def test_shape_suggestion_none_for_carton():
    gray = cv2.cvtColor(package_frame(), cv2.COLOR_BGR2GRAY)
    pkg = geometry.package_region(gray)
    assert geometry.suggest_shape(gray, pkg) == ("", 0.0)


# ------------------------------------------------------------------ stage
def test_stage_degrades_to_noop_on_noise():
    rng = np.random.default_rng(9)
    frame = rng.integers(0, 200, (700, 900, 3), np.uint8)
    ctx = PipelineContext()
    rep = s2_geometry_detect.run(ctx, frame)
    assert rep.ok and rep.crop is None and rep.origin == (0, 0)
    assert ctx.rois == [] and ctx.shape_detected == ""
    assert ctx.stages[-1].stage == "s2_geometry_detect"


def test_stage_crop_keeps_adjacent_fiducial():
    frame = package_frame()
    marker = aruco.generate_image(0, 120)
    frame[300:420, 600:720] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    ctx = PipelineContext()
    rep = s2_geometry_detect.run(ctx, frame)
    assert rep.crop is not None and rep.origin != (0, 0)
    crop_gray = cv2.cvtColor(rep.crop, cv2.COLOR_BGR2GRAY)
    assert aruco.detect_markers(crop_gray)       # card survived the crop


def test_stage_crop_excludes_distant_fiducial():
    frame = package_frame(size=(1100, 700))
    marker = aruco.generate_image(1, 120)
    frame[40:160, 940:1060] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    ctx = PipelineContext()
    rep = s2_geometry_detect.run(ctx, frame)
    assert rep.crop is not None
    crop_gray = cv2.cvtColor(rep.crop, cv2.COLOR_BGR2GRAY)
    assert aruco.detect_markers(crop_gray) == []
    assert "fiducial" in rep.detail


def test_stage_reports_rois():
    frame, _ = barcode_frame()
    ctx = PipelineContext()
    s2_geometry_detect.run(ctx, frame)
    kinds = {r["roi"] for r in ctx.rois}
    assert kinds == {"PACKAGE", "BARCODE"}
    assert all(r["bbox"].w > 0 and 0.0 <= r["conf"] <= 1.0 for r in ctx.rois)


# --------------------------------------------------------- serialization
def test_result_serializes_geometry_rois():
    from netra_core.bridge.schema import result_from_context
    ctx = PipelineContext()
    ctx.rois = [{"roi": "PACKAGE", "bbox": BBox(10, 20, 30, 40), "conf": 0.8}]
    ctx.shape_detected = "cylindrical"
    g = result_from_context(ctx)["geometry"]
    assert g["shape"] == "cylindrical" and g["shape_detected"] == "cylindrical"
    assert g["rois"][0] == {"roi": "PACKAGE", "bbox": [10, 20, 30, 40],
                            "conf": 0.8}

    ctx2 = PipelineContext(shape_hint="pouch")
    ctx2.shape_detected = "cylindrical"
    assert result_from_context(ctx2)["geometry"]["shape"] == "pouch"


# ------------------------------------------------- pipeline offset wiring
def test_pipeline_offsets_evidence_back_to_submitted_space(monkeypatch):
    from netra_core.bridge.schema import scan_request_from_dict
    from netra_core.pipeline import run_scan

    frame = package_frame()
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")

    # tokens in CROP space (the fake engine receives the cropped frame)
    tokens = [
        _tok(60, 120, 150, 30, "Net Quantity:"),
        _tok(220, 120, 90, 30, "70 g"),
        _tok(60, 170, 60, 40, "MRP"),
        _tok(130, 170, 120, 40, "Rs 50.00"),
        _tok(260, 170, 200, 40, "(incl. of all taxes)"),
    ]
    monkeypatch.setitem(s4_ocr._ENGINES, "tesseract", lambda f: list(tokens))

    req, err = scan_request_from_dict({
        "image_b64": b64, "shape_hint": "rectangular",
        "options": {"package_height_cm": 12.0, "package_width_cm": 9.0}})
    assert err is None
    r = run_scan(req)

    assert r["error"] is None
    assert r["ocr"]["engines_used"] == ["tesseract"]
    assert "s2_geometry_detect" in r["timings_ms"]
    assert {x["roi"] for x in r["geometry"]["rois"]} >= {"PACKAGE"}
    # crop origin = package(150,100) - margin(40,50): bboxes shift by it
    bbox = r["fields"]["net_qty"]["bbox"]
    assert abs(bbox[0] - (60 + 110)) <= 6      # x: 60 + origin.x
    assert abs(bbox[1] - (120 + 50)) <= 6      # y: 120 + origin.y
    assert r["fields"]["net_qty"]["value"] == "70"
