"""Backend integration — guarded so the CORE suite stays green even when
the backend package isn't installed (module-level skip)."""
import pytest

pytest.importorskip("netra_backend")

import json                                                    # noqa: E402

from fastapi.testclient import TestClient                      # noqa: E402

from netra_backend import db                                   # noqa: E402
from netra_backend.app import app                              # noqa: E402
from netra_core import paths                                   # noqa: E402
from netra_core.dossier import crypto                          # noqa: E402
from netra_core.persistence import queue_db                    # noqa: E402
from netra_core.pipeline import run_demo_scan                  # noqa: E402
from netra_core.sync import client                             # noqa: E402

COMPLIANT = {
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


@pytest.fixture
def api(tmp_path):
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    db.reset(f"sqlite:///{tmp_path}/backend.db")
    yield TestClient(app)
    queue_db.reset()
    paths.set_data_dir(None)


env = api


def _envelope():
    r = run_demo_scan(dossier=True)
    if crypto.HAVE_CRYPTO:
        key = crypto.make_dev_key()
        from netra_core.pipeline import attach_signature
        attach_signature(r["scan_id"],
                         crypto.dev_sign(key, r["scan_id"],
                                         r["dossier"]["sha256"]),
                         crypto.make_dev_cert(key))
    return client.envelope_from_row(queue_db.get_db().get_scan(r["scan_id"]))


def test_ingest_and_idempotent_duplicate(api):
    env = _envelope()
    resp = api.post("/ingest", json=env)
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True
    assert resp.json()["duplicate"] is False
    again = api.post("/ingest", json=env)
    assert again.json()["duplicate"] is True


def test_ingest_rejects_retry_and_garbage(api):
    assert api.post("/ingest", json={"scan_id": "x"}).status_code == 400
    env = _envelope()
    env["verdict"] = "RETRY"
    assert api.post("/ingest", json=env).status_code == 422


def test_stats_and_top_rules(api):
    api.post("/ingest", json=_envelope())
    st = api.get("/stats").json()
    assert st["total"] == 1 and st["violation"] == 1 and st["signed"] == 1
    assert st["top_rules"][0]["rule"] == "13"
    assert st["top_rules"][0]["count"] >= 1


def test_heatmap_geojson(api):
    api.post("/ingest", json=_envelope())
    hm = api.get("/heatmap").json()
    assert hm["type"] == "FeatureCollection"
    assert len(hm["features"]) == 1            # demo scan carries GPS
    coords = hm["features"][0]["geometry"]["coordinates"]
    assert coords[0] == pytest.approx(72.8777)
    assert coords[1] == pytest.approx(19.0760)


def test_export_edakakhil_endpoint(api):
    env = _envelope()
    api.post("/ingest", json=env)
    r = api.post(f"/export/edakakhil/{env['scan_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["export"] == "edakakhil"
    assert len(body["case"]["violations"]) == 7
    assert body["case"]["respondent"]["name"] == "Global Foods"


def test_export_rejections(api):
    env = _envelope()
    api.post("/ingest", json=env)
    assert api.post("/export/edakakhil/unknown").status_code == 404
    assert api.post("/export/nch1915/unknown").status_code == 404


def test_export_requires_violation(api):
    r = run_demo_scan(label=COMPLIANT, dossier=True)     # PASS, no dossier
    env = client.envelope_from_row(queue_db.get_db().get_scan(r["scan_id"]))
    assert api.post("/ingest", json=env).status_code == 200
    assert api.post(f"/export/edakakhil/{r['scan_id']}").status_code == 400
    assert api.post(f"/export/nch1915/{r['scan_id']}").status_code == 400


def test_auth_with_gateway_token(api, monkeypatch):
    monkeypatch.setenv("NETRA_GATEWAY_TOKEN", "secret-token-123")
    env = _envelope()
    # without token -> 401
    assert api.post("/ingest", json=env).status_code == 401
    # with wrong token -> 401
    assert api.post("/ingest", json=env, headers={"Authorization": "Bearer wrong"}).status_code == 401
    # with valid token -> 200
    resp = api.post("/ingest", json=env, headers={"Authorization": "Bearer secret-token-123"})
    assert resp.status_code == 200


def test_ingest_rejects_contract_violating_result(api):
    env = _envelope()
    bad_result = dict(env["result"])
    bad_result.pop("verdict")   # violates contract
    env["result"] = bad_result
    resp = api.post("/ingest", json=env)
    assert resp.status_code == 422
    assert "violates bridge contract" in resp.json()["detail"]


def test_server_side_signature_verification_enforced(api):
    env = _envelope()
    # tamper with signature so it fails verification
    env["signature"] = "corrupted_sig_base64"
    resp = api.post("/ingest", json=env)
    assert resp.status_code == 422
    assert "signature invalid" in resp.json()["detail"]


def test_server_side_verification_ignores_client_sig_verified_flag(api):
    env = _envelope()
    # Client lies saying sig_verified is False when it is actually valid
    env["sig_verified"] = False
    resp = api.post("/ingest", json=env)
    assert resp.status_code == 200
    # Query scan from api
    scan_data = api.get(f"/scans/{env['scan_id']}").json()
    if crypto.HAVE_CRYPTO:
        # Computed server-side, not trusting client False
        assert scan_data["sig_verified"] is True

