import base64

import cv2
import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("pytesseract")

from netra_core.ocr import tesseract_bridge   # noqa: E402

pytestmark = pytest.mark.skipif(not tesseract_bridge.available(),
                                reason="tesseract binary not installed")

from netra_core.stages import s4_ocr           # noqa: E402
from netra_core.vision import aruco            # noqa: E402


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    from netra_core import paths
    from netra_core.persistence import queue_db
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    yield
    queue_db.reset()
    paths.set_data_dir(None)


def _canvas(texts, w=1000, h=1400):
    frame = np.full((h, w, 3), 250, np.uint8)
    y = 150
    for text in texts:
        cv2.putText(frame, text, (80, y), cv2.FONT_HERSHEY_SIMPLEX, 1.8,
                    (25, 25, 25), 4, cv2.LINE_AA)
        y += 120
    return frame


def test_reads_printed_text():
    engine = tesseract_bridge.make_engine()
    tokens = engine(_canvas(["Net Quantity: 70 g",
                             "MRP Rs 50.00 (incl. of all taxes)"]))
    assert len(tokens) >= 6
    joined = " ".join(t.text for t in tokens)
    assert "Quantity" in joined and "70" in joined
    assert all(0.0 <= t.conf <= 1.0 for t in tokens)
    assert all(t.engine == "tesseract" for t in tokens)
    for t in tokens:
        assert 0 <= t.bbox.x and t.bbox.x2 <= 1000
        assert 0 <= t.bbox.y and t.bbox.y2 <= 1400


def test_pipeline_end_to_end_with_fiducial():
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

    from netra_core.bridge.schema import scan_request_from_dict
    from netra_core.pipeline import run_scan
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    req, err = scan_request_from_dict({
        "image_b64": b64, "shape_hint": "rectangular",
        "options": {"package_height_cm": 14.0, "package_width_cm": 10.0}})
    assert err is None

    try:
        s4_ocr.register_engine("tesseract", tesseract_bridge.make_engine())
        r = run_scan(req)
    finally:
        s4_ocr._ENGINES.pop("tesseract", None)

    assert r["error"] is None
    assert r["quality"]["ok"] is True
    assert "s3_calibration" in r["timings_ms"]
    assert r["ocr"]["engines_used"] == ["tesseract"]
    assert len(r["ocr"]["tokens"]) >= 10
    assert "net_qty" in r["fields"]
    assert r["fields"]["net_qty"]["unit"] == "g"
