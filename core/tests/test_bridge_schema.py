import base64
import json
import math
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("cv2")

from netra_core.bridge import chaquopy_api          # noqa: E402
from netra_core.bridge.schema import (              # noqa: E402
    RESULT_KEYS, SCHEMA_VERSION, STAGE_NAMES,
    ping_payload, scan_request_from_dict,
)
import netra_core.pipeline as pipeline_module       # noqa: E402
from netra_core.pipeline import run_demo_scan, run_scan   # noqa: E402


def _walk(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)
    else:
        yield node


def _image_b64(frame: np.ndarray) -> str:
    ok, buf = cv2_imencode(frame)
    assert ok
    return base64.b64encode(buf.tobytes()).decode()


def cv2_imencode(frame):
    import cv2
    return cv2.imencode(".jpg", frame)


# ------------------------------------------------------------- ping / request
def test_ping_payload():
    p = ping_payload()
    assert p["schema_version"] == SCHEMA_VERSION
    assert p["channel"] == "netra.core"
    assert "s6_metrology" in p["capabilities"]["stages_implemented"]


def test_request_missing_image():
    req, err = scan_request_from_dict({})
    assert req is None and err["code"] == "BAD_REQUEST"


def test_request_bad_shape_hint():
    req, err = scan_request_from_dict({"image_b64": "AAAA", "shape_hint": "hexagonal"})
    assert req is None and err["code"] == "BAD_REQUEST"


def test_request_unsupported_version():
    req, err = scan_request_from_dict({"schema_version": 99, "image_b64": "AAAA"})
    assert req is None and err["code"] == "UNSUPPORTED_VERSION"


def test_request_bad_captured_utc():
    req, err = scan_request_from_dict({"image_b64": "AAAA", "captured_utc": "not-a-date"})
    assert req is None and err["code"] == "BAD_REQUEST"


def test_request_ok_with_options():
    req, err = scan_request_from_dict(
        {"image_b64": "AAAA", "shape_hint": "pouch",
         "options": {"institutional": True, "commodity": "biscuits"}})
    assert err is None
    assert req.shape_hint == "pouch"
    assert req.options["institutional"] is True
    assert req.options["commodity"] == "biscuits"


# ----------------------------------------------------------- result freezing
def test_result_keys_frozen():
    r = run_demo_scan()
    assert set(r) == set(RESULT_KEYS)          # the contract freeze


def test_result_json_native_and_finite():
    r = run_demo_scan()
    json.dumps(r, allow_nan=False)             # raises on NaN/Inf
    for leaf in _walk(r):
        assert leaf is None or isinstance(leaf, (str, int, float, bool))
        if isinstance(leaf, float):
            assert math.isfinite(leaf)


def test_demo_verdict_and_summary():
    r = run_demo_scan()
    assert r["verdict"] == "VIOLATION"
    s, checks = r["summary"], r["checks"]
    assert s["total"] == len(checks) == 11
    assert s["fail"] == sum(1 for c in checks if c["status"] == "FAIL") == 7
    assert s["pass"] + s["fail"] + s["na"] == s["total"]


def test_money_and_quantities_are_strings():
    f = run_demo_scan()["fields"]
    assert isinstance(f["mrp"]["value"], str) and f["mrp"]["value"] == "14.00"
    assert f["net_qty"]["value"] == "70" and f["net_qty"]["unit"] == "g"


def test_bbox_is_four_ints():
    bbox = run_demo_scan()["fields"]["net_qty"]["bbox"]
    assert isinstance(bbox, list) and len(bbox) == 4
    assert all(isinstance(v, int) for v in bbox)


def test_checks_shape_and_citations():
    for c in run_demo_scan()["checks"]:
        assert set(c) == {"rule", "status", "message", "citation", "evidence_bbox"}
        assert c["citation"]                       # never empty in the report UI


def test_timings_within_canonical_stages():
    r = run_demo_scan()
    assert set(r["timings_ms"]) <= set(STAGE_NAMES)


def test_quality_nulls_when_s1_not_run():
    q = run_demo_scan()["quality"]
    assert q["ok"] is None and q["prompts"] == []


# ------------------------------------------------------------- scan pipeline
def test_run_scan_blurred_frame_is_retry():
    b64 = _image_b64(np.zeros((480, 640, 3), np.uint8))
    req, err = scan_request_from_dict({"image_b64": b64, "shape_hint": "rectangular"})
    r = run_scan(req)
    assert err is None
    assert r["verdict"] == "RETRY" and r["error"] is None
    assert r["quality"]["ok"] is False and r["quality"]["prompts"]


def test_run_scan_bad_base64():
    req, _ = scan_request_from_dict({"image_b64": "@@@"})
    r = run_scan(req)
    assert r["verdict"] == "RETRY"
    assert r["error"]["code"] == "DECODE_ERROR"


def test_run_scan_retries_without_calibration():
    rng = np.random.default_rng(7)
    b64 = _image_b64(rng.integers(0, 200, (480, 640, 3), dtype=np.uint8))
    req, _ = scan_request_from_dict({"image_b64": b64})
    r = run_scan(req)
    assert r["quality"]["ok"] is True                     # s1 passed
    assert "s2_geometry_detect" in r["timings_ms"]        # deterministic s2 ran
    assert "s3_calibration" in r["timings_ms"]
    assert r["verdict"] == "RETRY" and r["error"] is None
    assert any("fiducial" in p.lower() for p in r["quality"]["prompts"])


def test_run_scan_internal_error_envelope(monkeypatch):
    def boom(ctx, frame):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(pipeline_module, "_STAGES_IN_ORDER",
                        (("s1_frame_quality", boom),))
    b64 = _image_b64(np.zeros((480, 640, 3), np.uint8))
    req, _ = scan_request_from_dict({"image_b64": b64})
    r = run_scan(req)
    assert r["verdict"] == "RETRY"
    assert r["error"]["code"] == "INTERNAL"
    assert r["error"]["stage"] == "s1_frame_quality"


def test_request_rejects_bad_option_value():
    req, err = scan_request_from_dict(
        {"image_b64": "AAAA", "options": {"package_height_cm": "tall"}})
    assert req is None and err["code"] == "BAD_REQUEST"


def test_request_accepts_calibration_options():
    req, err = scan_request_from_dict({
        "image_b64": "AAAA",
        "options": {"package_height_cm": 12.5, "package_width_cm": 8,
                    "blown": True, "marker_side_mm": 40}})
    assert err is None
    assert req.options["package_height_cm"] == 12.5
    assert req.options["blown"] is True
    assert req.options["package_width_cm"] == 8.0


# --------------------------------------------------------- chaquopy + server
def test_chaquopy_scan_rejects_bad_json():
    r = json.loads(chaquopy_api.scan("{not json"))
    assert r["error"]["code"] == "BAD_REQUEST"


def test_chaquopy_scan_blur_image_round_trip():
    b64 = _image_b64(np.zeros((480, 640, 3), np.uint8))
    r = json.loads(chaquopy_api.scan(json.dumps({"image_b64": b64})))
    assert r["schema_version"] == SCHEMA_VERSION
    assert r["verdict"] == "RETRY" and r["quality"]["ok"] is False


def test_server_health_and_demo():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from netra_core.bridge.server import app

    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["schema_version"] == SCHEMA_VERSION

    demo = client.post("/scan/demo", json={})
    assert demo.status_code == 200
    body = demo.json()
    assert body["verdict"] == "VIOLATION" and body["summary"]["total"] == 11


def test_demo_uses_real_extraction():
    r = run_demo_scan()
    assert set(r["timings_ms"]) == {"s4_ocr", "s5_field_extract", "s6_metrology"}
    assert r["ocr"]["tokens"] and r["ocr"]["engines_used"] == ["mlkit"]
    assert r["fields"]["net_qty"]["conf"] > 0.0


def test_demo_checks_carry_evidence():
    r = run_demo_scan()
    evidence = [c["evidence_bbox"] for c in r["checks"]
                if c["rule"] == "6(1)(c)"]
    assert evidence and evidence[0] is not None and len(evidence[0]) == 4


def test_demo_dossier_flag_contract(tmp_path):
    from netra_core import paths
    from netra_core.persistence import queue_db as qdb
    paths.set_data_dir(tmp_path / "nd")
    qdb.reset()
    try:
        r = run_demo_scan(dossier=True)
        assert r["verdict"] == "VIOLATION" and r["summary"]["total"] == 11
        assert r["dossier"]["sha256"] and len(r["dossier"]["sha256"]) == 64
        assert Path(r["dossier"]["pdf_path"]).exists()
        assert "s7_dossier" in r["timings_ms"]
    finally:
        qdb.reset()
        paths.set_data_dir(None)

