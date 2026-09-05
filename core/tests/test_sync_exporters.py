import pytest

from netra_core import paths
from netra_core.dossier import crypto
from netra_core.persistence import queue_db
from netra_core.pipeline import attach_signature, run_demo_scan
from netra_core.sync import client, exporters

needs_crypto = pytest.mark.skipif(
    not crypto.HAVE_CRYPTO, reason="cryptography not installed")


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    yield
    queue_db.reset()
    paths.set_data_dir(None)


def _row():
    r = run_demo_scan(dossier=True)
    return queue_db.get_db().get_scan(r["scan_id"])


def _signed_row():
    r = run_demo_scan(dossier=True)
    key = crypto.make_dev_key()
    attach_signature(r["scan_id"],
                     crypto.dev_sign(key, r["scan_id"],
                                     r["dossier"]["sha256"]),
                     crypto.make_dev_cert(key))
    return queue_db.get_db().get_scan(r["scan_id"])


@needs_crypto
def test_edakakhil_payload_shape():
    env = client.envelope_from_row(_signed_row())
    p = exporters.edakakhil_payload(env)
    assert p["export"] == "edakakhil"
    case = p["case"]
    assert case["statute"]["rules"] == \
        "Legal Metrology (Packaged Commodities) Rules, 2011"
    assert len(case["violations"]) == 7
    assert case["violations"][0]["rule"] == "13"
    ev = case["evidence"]
    assert ev["signature_verified_by_core"] is True
    assert ev["dossier_signature"] and ev["dossier_sha256"]


@needs_crypto
def test_respondent_extraction():
    env = client.envelope_from_row(_signed_row())
    resp = exporters.edakakhil_payload(env)["case"]["respondent"]
    assert resp["name"] == "Global Foods"
    assert "Mumbai 400001" in resp["address_as_declared"]


def test_pin_zone_from_ledger_row():
    env = client.envelope_from_row(_row())       # PIN 400001 -> zone 4
    zone = exporters.nch1915_payload(env)["complaint"]["pin_zone"]
    assert zone.startswith("Maharashtra")


def test_nch1915_payload_shape():
    p = exporters.nch1915_payload(client.envelope_from_row(_row()))
    c = p["complaint"]
    assert c["brand_or_product"] == "Instant Masala Noodles"
    assert "7 statutory non-compliance" in c["description"]
    assert "Rule 13" in c["description"]
    assert c["evidence"]["dossier_signature"] is None


def test_exports_on_envelope_and_row_agree():
    row = _row()
    a = exporters.edakakhil_payload(client.envelope_from_row(row))
    b = exporters.edakakhil_payload(row)
    assert a["case"]["violations"] == b["case"]["violations"]
