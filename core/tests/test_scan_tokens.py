import base64
import hashlib
import io
import json
import math

import pytest

from PIL import Image

from netra_core import paths
from netra_core.bridge.schema import scan_tokens_request_from_dict
from netra_core.context import BBox, OCRToken
from netra_core.persistence import queue_db
from netra_core.pipeline import _DEMO_TOKENS, _tokens_from_label, run_scan_tokens
from netra_core.qa import contract

GEOM = {"shape": "pouch", "mm_per_px": 0.04, "pda_cm2": 80.0,
        "pda_method": "solvePnP-aruco"}

COMPLIANT_LABEL = {
    "product_name": "Instant Masala Noodles",
    "net_qty": "Net Quantity: 70 g",
    "mrp": "MRP Rs 50.00 (incl. of all taxes)",
    "usp": "Unit Sale Price Rs 0.71 / g",
    "mfg_date": "MFG 08/2026",
    "mfg_address": "Mfd. by: Tasty Foods Ltd., Plot 21, Goa 403001",
    "origin": "Made in India",
    "consumer_care": "Consumer Care: Tasty Foods, Mumbai 400050, "
                     "Tel: 1800-123-4567, care@tasty.in",
}


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    yield
    queue_db.reset()
    paths.set_data_dir(None)


def _body(tokens, **extra):
    body = {"tokens": [{"text": t.text, "bbox": t.bbox.to_list(),
                        "conf": t.conf, "engine": t.engine, "lang": t.lang}
                       for t in tokens]}
    body.update(extra)
    return body


def _run(body):
    req, err = scan_tokens_request_from_dict(body)
    assert err is None, err
    return run_scan_tokens(req)


def _tiny_jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (240, 240, 240)).save(buf, "JPEG")
    data = buf.getvalue()
    return base64.b64encode(data).decode(), hashlib.sha256(data).hexdigest()


def test_violation_verdict_from_tokens():
    r = _run(_body(_DEMO_TOKENS, geometry=GEOM))
    assert r["verdict"] == "VIOLATION"
    assert r["summary"] == {"total": 11, "pass": 4, "fail": 7, "na": 0}
    assert r["geometry"]["pda_cm2"] == 80.0
    assert r["quality"]["ok"] is None
    ev = [c for c in r["checks"] if c["rule"] == "6(1)(c)"][0]
    assert ev["evidence_bbox"] is not None
    assert contract.validate_scan_result(r) == []


def test_dossier_generated_on_tokens_path():
    from pathlib import Path
    r = _run(_body(_DEMO_TOKENS, geometry=GEOM))
    assert r["dossier"] is not None
    p = Path(r["dossier"]["pdf_path"])
    assert p.exists() and p.read_bytes()[:5] == b"%PDF-"
    row = queue_db.get_db().get_scan(r["scan_id"])
    assert row["verdict"] == "VIOLATION"
    assert row["dossier_sha256"] == r["dossier"]["sha256"]


def test_compliant_label_passes():
    # tokens are h=30px; mm_per_px 0.05 -> 1.5 mm; PDA 50 cm2 -> 1.0 mm min
    geom = {"mm_per_px": 0.05, "pda_cm2": 50.0, "pda_method": "demo"}
    r = _run(_body(_tokens_from_label(COMPLIANT_LABEL), geometry=geom))
    assert r["verdict"] == "PASS", [c for c in r["checks"]
                                    if c["status"] == "FAIL"]
    assert r["dossier"] is None                 # PASS: no dossier by default
    assert queue_db.get_db().status()["total"] == 1


def test_quality_gate_short_circuits_to_retry():
    r = _run(_body(_DEMO_TOKENS,
                   quality={"ok": False, "prompts": ["Tilt 15 degrees"]}))
    assert r["verdict"] == "RETRY" and r["error"] is None
    assert r["quality"]["prompts"] == ["Tilt 15 degrees"]
    assert r["summary"]["total"] == 0
    assert queue_db.get_db().status()["total"] == 0


def test_quality_gate_synthesizes_prompt_when_silent():
    r = _run(_body(_DEMO_TOKENS, quality={"ok": False}))
    assert r["quality"]["prompts"]              # validator law: no silent RETRY
    assert contract.validate_scan_result(r) == []


def test_non_statutory_tokens_is_retry_with_prompt():
    r = _run(_body([OCRToken("Fresh Milk", BBox(50, 50, 200, 40), 0.95)]))
    assert r["verdict"] == "RETRY"
    assert any("declaration" in p.lower() for p in r["quality"]["prompts"])


def test_geometry_absent_rule7_na():
    r = _run(_body(_DEMO_TOKENS))
    assert r["verdict"] == "VIOLATION"
    rule7 = [c for c in r["checks"] if c["rule"] == "7"]
    assert rule7 and all(c["status"] == "NA" for c in rule7)
    assert r["geometry"] is None


def test_glyphs_activate_rule73():
    r = _run(_body(_DEMO_TOKENS, geometry=GEOM,
                   glyphs=[{"glyph": "M", "height_mm": 3.0, "width_mm": 0.5}]))
    assert "7(3)" in {c["rule"] for c in r["checks"] if c["status"] == "FAIL"}


def test_bad_token_bbox_rejected():
    req, err = scan_tokens_request_from_dict(
        {"tokens": [{"text": "x", "bbox": [1, 2, 3]}]})
    assert req is None and err["code"] == "BAD_REQUEST"


def test_unknown_engine_rejected():
    req, err = scan_tokens_request_from_dict(
        {"tokens": [{"text": "x", "bbox": [1, 2, 3, 4], "engine": "easyocr"}]})
    assert req is None and err["code"] == "BAD_REQUEST"


def test_empty_tokens_rejected():
    req, err = scan_tokens_request_from_dict({"tokens": []})
    assert req is None and err["code"] == "BAD_REQUEST"


def test_image_round_trip_and_dossier():
    b64, sha = _tiny_jpeg()
    r = _run(_body(_DEMO_TOKENS, geometry=GEOM, image_b64=b64,
                   image_sha256=sha))
    assert r["error"] is None and r["dossier"] is not None


def test_image_sha_mismatch_rejected():
    b64, _sha = _tiny_jpeg()
    r = _run(_body(_DEMO_TOKENS, geometry=GEOM, image_b64=b64,
                   image_sha256="0" * 64))
    assert r["error"]["code"] == "BAD_REQUEST"


def test_server_scan_tokens_endpoint():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from netra_core.bridge.server import app
    client = TestClient(app)
    resp = client.post("/scan/tokens", json=_body(_DEMO_TOKENS, geometry=GEOM))
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "VIOLATION"
    bad = client.post("/scan/tokens", json={"tokens": []})
    assert bad.json()["error"]["code"] == "BAD_REQUEST"


def test_chaquopy_scan_tokens_round_trip():
    from netra_core.bridge import chaquopy_api
    out = json.loads(chaquopy_api.scan_tokens(
        json.dumps(_body(_DEMO_TOKENS, geometry=GEOM))))
    assert out["verdict"] == "VIOLATION" and out["schema_version"] == 1
    bad = json.loads(chaquopy_api.scan_tokens("{nope"))
    assert bad["error"]["code"] == "BAD_REQUEST"


def test_contract_validator_on_requests():
    assert contract.validate_scan_tokens_request(
        _body(_DEMO_TOKENS, geometry=GEOM)) == []
    bad = _body(_DEMO_TOKENS)
    bad["tokens"][0]["bbox"] = [1, 2, 3]
    assert contract.validate_scan_tokens_request(bad)
    bad2 = _body(_DEMO_TOKENS)
    bad2["tokens"][0]["engine"] = "easyocr"
    assert contract.validate_scan_tokens_request(bad2)


def test_pda_from_inspector_dims_not_geometry():
    # no pda_cm2 in geometry — dims in options must carry it (Rule 7 interim)
    r = _run(_body(_tokens_from_label(COMPLIANT_LABEL),
                   geometry={"mm_per_px": 0.05},
                   options={"package_height_cm": 20.0, "package_width_cm": 13.0}))
    assert r["geometry"]["pda_cm2"] == 260.0
    assert r["geometry"]["pda_method"] == "inspector-dims"
    # tokens h=30px x 0.05 = 1.5 mm; PDA 260 cm2 -> band 3 (2.5 mm min) -> FAIL
    assert r["verdict"] == "VIOLATION"


def test_pda_cylindrical_from_dims():
    r = _run(_body(_DEMO_TOKENS, shape_hint="cylindrical",
                   options={"package_height_cm": 10.0,
                            "package_diameter_cm": 6.0}))
    assert r["geometry"]["pda_cm2"] == pytest.approx(
        0.4 * 10 * math.pi * 6, rel=1e-3)
    assert r["geometry"]["pda_method"] == "inspector-dims"


def test_pda_sanity_bounds_drop_garbage_dims():
    r = _run(_body(_DEMO_TOKENS,
                   options={"package_height_cm": 300.0,
                            "package_width_cm": 250.0}))
    assert r["geometry"] is None          # 75,000 cm2 -> out of sanity range


def test_dossier_on_pass_option_flows_through():
    geom = {"mm_per_px": 0.05, "pda_cm2": 50.0}
    r = _run(_body(_tokens_from_label(COMPLIANT_LABEL), geometry=geom,
                   options={"dossier_on_pass": True}))
    assert r["verdict"] == "PASS"
    assert r["dossier"] is not None and len(r["dossier"]["sha256"]) == 64
    assert queue_db.get_db().status()["dossiers"] == 1


def test_ledger_failure_warns_instead_of_lying(monkeypatch):
    from netra_core.persistence import queue_db
    def boom():
        raise RuntimeError("disk full")
    monkeypatch.setattr(queue_db, "get_db", boom)
    r = _run(_body(_DEMO_TOKENS, geometry=GEOM))
    assert r["verdict"] == "VIOLATION"              # audit result survives
    assert any("ledger" in p.lower()
               for p in r["quality"]["prompts"])    # failure is surfaced
    assert contract.validate_scan_result(r) == []   # still contract-valid


