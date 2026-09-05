import base64
import hashlib
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("cv2")

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / \
    "make_synth_fixtures.py"
_spec = importlib.util.spec_from_file_location("make_synth_fixtures", _SCRIPT)
synth = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(synth)

from netra_core.ocr import tesseract_bridge   # noqa: E402
from netra_core.qa import golden              # noqa: E402


def _image_hashes(root: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "labels").glob("*.jpg"))}


def test_generate_writes_seven_fixtures_with_valid_gt(tmp_path):
    gt = synth.generate(tmp_path)
    assert len(gt) == 7
    assert len(list((tmp_path / "labels").glob("*.jpg"))) == 7
    for key, entry in gt.items():
        assert golden.validate_entry(key, entry) == []
        assert (tmp_path / "labels" / f"{key}.jpg").exists()
    assert gt["S02_gms"]["expect_fail"] == ["13", "6(1)(c)"]
    assert gt["S07_blur"]["fields"] == gt["S01_clean"]["fields"]


def test_generation_is_deterministic(tmp_path):
    synth.generate(tmp_path / "a")
    synth.generate(tmp_path / "b")
    assert _image_hashes(tmp_path / "a") == _image_hashes(tmp_path / "b")


@pytest.mark.skipif(not tesseract_bridge.available(),
                    reason="tesseract binary not installed")
def test_clean_fixture_passes_full_pipeline(tmp_path):
    from netra_core import paths
    from netra_core.bridge.schema import scan_request_from_dict
    from netra_core.persistence import queue_db
    from netra_core.pipeline import run_scan
    from netra_core.stages import s4_ocr

    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    try:
        synth.generate(tmp_path / "fx")
        img = (tmp_path / "fx" / "labels" / "S01_clean.jpg").read_bytes()
        req, err = scan_request_from_dict({
            "image_b64": base64.b64encode(img).decode("ascii"),
            "shape_hint": "rectangular",
            "options": {"package_height_cm": 20.0,
                        "package_width_cm": 16.0}})
        assert err is None
        try:
            s4_ocr.register_engine("tesseract",
                                   tesseract_bridge.make_engine())
            r = run_scan(req)
        finally:
            s4_ocr._ENGINES.pop("tesseract", None)
        assert r["error"] is None, r["error"]
        assert r["fields"]["net_qty"]["value"] == "200"
        assert r["fields"]["mrp"]["value"] == "50.00"
        assert r["fields"]["usp"]["value"] == "0.25"
        assert r["verdict"] == "PASS", [c for c in r["checks"]
                                        if c["status"] == "FAIL"]
    finally:
        queue_db.reset()
        paths.set_data_dir(None)
