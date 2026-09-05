import json
import re

import pytest

from netra_core import paths
from netra_core.dossier import crypto
from netra_core.persistence import queue_db
from netra_core.pipeline import attach_signature, run_demo_scan

needs_crypto = pytest.mark.skipif(
    not crypto.HAVE_CRYPTO, reason="cryptography not installed")


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    yield
    queue_db.reset()
    paths.set_data_dir(None)


def _demo_scan():
    return run_demo_scan(dossier=True)


def _sign(scan_id, sha, key=None):
    key = key or crypto.make_dev_key()
    return (crypto.dev_sign(key, scan_id, sha),
            crypto.make_dev_cert(key), key)


@needs_crypto
def test_round_trip_accepted_and_verified():
    r = _demo_scan()
    sig, cert, _ = _sign(r["scan_id"], r["dossier"]["sha256"])
    resp = attach_signature(r["scan_id"], sig, cert)
    assert resp["accepted"] is True
    assert resp["sig_status"] == "signed" and resp["verified"] is True
    row = queue_db.get_db().get_scan(r["scan_id"])
    assert row["signature"] == sig and row["sig_verified"] == 1
    assert queue_db.get_db().status()["signed"] == 1


@needs_crypto
def test_result_json_updated_after_signing():
    r = _demo_scan()
    sig, cert, _ = _sign(r["scan_id"], r["dossier"]["sha256"])
    attach_signature(r["scan_id"], sig, cert)
    stored = json.loads(queue_db.get_db().get_scan(r["scan_id"])["result_json"])
    assert stored["dossier"]["signed"] is True
    assert stored["dossier"]["sig_status"] == "signed"


@needs_crypto
def test_wrong_payload_rejected():
    r = _demo_scan()
    key = crypto.make_dev_key()
    bad = crypto.dev_sign(key, r["scan_id"], "0" * 64)   # wrong hash
    resp = attach_signature(r["scan_id"], bad, crypto.make_dev_cert(key))
    assert resp["accepted"] is False
    assert resp["error"]["code"] == "VERIFY_FAILED"
    # correct signature still accepted afterwards
    sig, cert, _ = _sign(r["scan_id"], r["dossier"]["sha256"])
    assert attach_signature(r["scan_id"], sig, cert)["accepted"] is True


@needs_crypto
def test_resign_rejected():
    r = _demo_scan()
    sig, cert, _ = _sign(r["scan_id"], r["dossier"]["sha256"])
    attach_signature(r["scan_id"], sig, cert)
    resp = attach_signature(r["scan_id"], sig, cert)
    assert resp["accepted"] is False
    assert resp["error"]["code"] == "ALREADY_SIGNED"


def test_unknown_scan_not_found():
    resp = attach_signature("deadbeef", "sig", "cert")
    assert resp["error"]["code"] == "NOT_FOUND"


def test_missing_arguments_bad_request():
    assert attach_signature("", "sig", "cert")["error"]["code"] == "BAD_REQUEST"
    assert attach_signature("id", "", "cert")["error"]["code"] == "BAD_REQUEST"
    assert attach_signature("id", "sig", None)["error"]["code"] == "BAD_REQUEST"


def test_no_dossier_scan_rejected():
    r = run_demo_scan(label={"net_qty": "Net Quantity: 70 g"}, dossier=True)
    row = queue_db.get_db().get_scan(r["scan_id"])
    if row["dossier_sha256"] is None:
        resp = attach_signature(r["scan_id"], "sig", "cert")
        assert resp["error"]["code"] == "NO_DOSSIER"


@needs_crypto
def test_server_endpoint_round_trip():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from netra_core.bridge.server import app

    r = _demo_scan()
    sig, cert, _ = _sign(r["scan_id"], r["dossier"]["sha256"])
    client = TestClient(app)
    resp = client.post("/attach_signature",
                       json={"scan_id": r["scan_id"], "signature": sig,
                             "cert_pem": cert})
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] and body["sig_status"] == "signed"
    st = client.get("/queue/status").json()
    assert st["signed"] == 1 and st["total"] == 1


@needs_crypto
def test_chaquopy_endpoint_round_trip():
    from netra_core.bridge import chaquopy_api
    r = _demo_scan()
    sig, cert, _ = _sign(r["scan_id"], r["dossier"]["sha256"])
    out = json.loads(chaquopy_api.attach_signature(json.dumps(
        {"scan_id": r["scan_id"], "signature": sig, "cert_pem": cert})))
    assert out["accepted"] and out["verified"]


def test_signature_payload_format_is_pinned():
    """The payload law — mirrored in NetraKeystore.kt and BRIDGE_CONTRACT
    section 8. If this regex and the Kotlin string ever disagree, the
    Android round-trip breaks; this test is the tripwire."""
    payload = crypto.sign_payload("a" * 32, "b" * 64).decode("utf-8")
    assert re.fullmatch(r"NETRA-DOSSIER-v1\|[0-9a-f]{32}\|[0-9a-f]{64}", payload)
