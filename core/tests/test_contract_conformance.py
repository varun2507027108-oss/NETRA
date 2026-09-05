import base64
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("cv2")
import cv2                                            # noqa: E402

import netra_core.pipeline as pipeline_module         # noqa: E402
from netra_core import paths                          # noqa: E402
from netra_core.bridge.schema import (SCHEMA_VERSION, ping_payload,   # noqa: E402
                                       scan_request_from_dict)
from netra_core.context import BBox, OCRToken         # noqa: E402
from netra_core.dossier import crypto                 # noqa: E402
from netra_core.persistence import queue_db           # noqa: E402
from netra_core.pipeline import (attach_signature,    # noqa: E402
                                 run_demo_scan, run_scan)
from netra_core.qa import contract                    # noqa: E402
from netra_core.stages import s4_ocr                  # noqa: E402
from netra_core.sync import client as sync_client     # noqa: E402


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    yield
    queue_db.reset()
    paths.set_data_dir(None)


def _b64(frame):
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _run(frame, options=None):
    req, err = scan_request_from_dict({"image_b64": _b64(frame),
                                       "options": options or {}})
    assert err is None
    return run_scan(req)


# ------------------------------------------------------- positive: the law
def test_demo_result_conforms():
    assert contract.validate_scan_result(run_demo_scan()) == []


def test_demo_dossier_result_conforms():
    r = run_demo_scan(dossier=True)
    assert contract.validate_scan_result(r) == []
    assert r["dossier"]["sig_status"] == "pending"


def test_blur_retry_conforms_and_carries_prompts():
    r = _run(np.zeros((480, 640, 3), np.uint8))
    assert r["verdict"] == "RETRY" and r["error"] is None
    assert r["quality"]["prompts"]
    assert contract.validate_scan_result(r) == []


def test_glare_retry_populates_glare_bbox():
    rng = np.random.default_rng(4)
    frame = rng.integers(0, 120, (480, 640, 3), dtype=np.uint8)
    frame[100:160, 300:420] = 255
    r = _run(frame)
    assert r["verdict"] == "RETRY"
    assert r["quality"]["glare_bbox"] is not None
    assert len(r["quality"]["glare_bbox"]) == 4
    assert contract.validate_scan_result(r) == []


def test_decode_error_conforms():
    req, _ = scan_request_from_dict({"image_b64": "@@@"})
    r = run_scan(req)
    assert r["error"]["code"] == "DECODE_ERROR"
    assert contract.validate_scan_result(r) == []


def test_internal_error_conforms(monkeypatch):
    def boom(ctx, frame):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(pipeline_module, "_STAGES_IN_ORDER",
                        (("s1_frame_quality", boom),))
    r = _run(np.zeros((480, 640, 3), np.uint8))
    assert r["error"]["code"] == "INTERNAL"
    assert contract.validate_scan_result(r) == []


def test_no_fiducial_retry_conforms():
    rng = np.random.default_rng(7)
    r = _run(rng.integers(0, 200, (480, 640, 3), dtype=np.uint8))
    assert r["verdict"] == "RETRY" and r["error"] is None
    assert r["quality"]["prompts"]
    assert contract.validate_scan_result(r) == []


def test_zero_text_retry_carries_prompt():
    rng = np.random.default_rng(11)
    r = _run(rng.integers(0, 200, (480, 640, 3), dtype=np.uint8),
             options={"package_height_cm": 12.0, "package_width_cm": 9.0})
    assert r["verdict"] == "RETRY" and r["error"] is None
    assert any("text" in p.lower() for p in r["quality"]["prompts"])
    assert contract.validate_scan_result(r) == []


def test_anchor_only_tokens_retry_carries_prompt(monkeypatch):
    # tokens decoded, but nothing statutory recognizable (only the word
    # "MRP", no value) -> s5 must explain itself
    monkeypatch.setitem(s4_ocr._ENGINES, "tesseract",
                        lambda f: [OCRToken("MRP", BBox(50, 50, 80, 30),
                                            0.9, "tesseract", "en")])
    rng = np.random.default_rng(13)
    r = _run(rng.integers(100, 170, (480, 640, 3), dtype=np.uint8),
             options={"package_height_cm": 12.0, "package_width_cm": 9.0})
    assert r["verdict"] == "RETRY"
    assert any("declaration" in p.lower() for p in r["quality"]["prompts"])
    assert contract.validate_scan_result(r) == []


def test_ping_conforms():
    assert contract.validate_ping(ping_payload()) == []


def test_sync_summaries_conform():
    assert contract.validate_sync_summary(sync_client.sync_now()) == []

    class _OK:
        def post(self, url, payload, headers=None, timeout=10.0):
            return 200, {"accepted": True}

    run_demo_scan(dossier=True)
    s = sync_client.SyncClient("http://gw",
                               transport=_OK()).sync_once().to_dict()
    assert s["synced"] >= 1
    assert contract.validate_sync_summary(s) == []


def test_sig_responses_conform():
    for resp in (attach_signature("", "s", "c"),
                 attach_signature("0" * 32, "s", "c")):
        assert contract.validate_sig_response(resp) == []
    if crypto.HAVE_CRYPTO:
        r = run_demo_scan(dossier=True)
        key = crypto.make_dev_key()
        ok = attach_signature(r["scan_id"],
                              crypto.dev_sign(key, r["scan_id"],
                                              r["dossier"]["sha256"]),
                              crypto.make_dev_cert(key))
        assert ok["accepted"]
        assert contract.validate_sig_response(ok) == []


def test_queue_status_conforms():
    st = {"schema_version": SCHEMA_VERSION, **queue_db.get_db().status()}
    assert contract.validate_queue_status(st) == []


def test_record_contract_fixtures_round_trip(tmp_path):
    script = Path(__file__).resolve().parent.parent / "scripts" / \
        "record_contract_fixtures.py"
    spec = importlib.util.spec_from_file_location("rcf", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    written = mod.record(tmp_path)
    assert len(written) >= 9
    for name in ("ping.json", "scan_violation.json",
                 "scan_violation_dossier.json", "scan_retry_blur.json",
                 "scan_error_decode.json", "sync_summary_success.json",
                 "sync_summary_not_configured.json",
                 "attach_signature_responses.json", "queue_status.json"):
        assert (tmp_path / name).exists(), name
    r = json.loads((tmp_path / "scan_violation.json").read_text("utf-8"))
    assert contract.validate_scan_result(r) == []
    sigs = json.loads((tmp_path / "attach_signature_responses.json")
                      .read_text("utf-8"))
    for resp in sigs.values():
        assert contract.validate_sig_response(resp) == []


# --------------------------------------------------- negative: law bites
@pytest.fixture()
def demo():
    return run_demo_scan()


def _mutate(demo, fn):
    r = copy.deepcopy(demo)
    fn(r)
    return r


def test_missing_key(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r.pop("summary")))


def test_unknown_key(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r.update(extra=1)))


def test_bad_verdict(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r.update(verdict="MAYBE")))


def test_nonfinite_total_ms(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r.update(total_ms=float("nan"))))


def test_fake_stage_in_timings(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r["timings_ms"].update(s9_magic=1.0)))


def test_bad_check_status(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r["checks"][0].update(status="MAYBE")))


def test_summary_mismatch(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r["summary"].update(fail=99)))


def test_bad_bbox_shape(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r["fields"]["net_qty"].update(bbox=[1, 2, 3])))


def test_numeric_field_value_rejected(demo):
    assert contract.validate_scan_result(
        _mutate(demo, lambda r: r["fields"]["mrp"].update(value=14.0)))


def test_error_with_non_retry_verdict_rejected(demo):
    def f(r):
        r["error"] = {"code": "INTERNAL", "message": "x", "stage": None}
    assert contract.validate_scan_result(_mutate(demo, f))


def test_silent_retry_rejected(demo):
    errs = contract.validate_scan_result(
        _mutate(demo, lambda r: r.update(verdict="RETRY")))
    assert any("prompts" in e for e in errs)


def test_bad_engine_enum(demo):
    def f(r):
        r["ocr"]["engines_used"] = ["easyocr"]
    assert contract.validate_scan_result(_mutate(demo, f))


def test_bad_roi_enum(demo):
    def f(r):
        r["geometry"]["rois"] = [{"roi": "SIDEPANEL",
                                  "bbox": [1, 2, 3, 4], "conf": 0.5}]
    assert contract.validate_scan_result(_mutate(demo, f))
