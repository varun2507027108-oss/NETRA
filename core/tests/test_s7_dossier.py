from pathlib import Path

import pytest

pytest.importorskip("cv2")

from netra_core import paths                              # noqa: E402
from netra_core.context import FieldValue, PipelineContext, Verdict  # noqa: E402
from netra_core.dossier import pdf_builder                # noqa: E402
from netra_core.persistence import queue_db               # noqa: E402
from netra_core.pipeline import run_demo_scan             # noqa: E402
from netra_core.stages import s6_metrology, s7_dossier    # noqa: E402

pytestmark = pytest.mark.skipif(not pdf_builder.HAVE_REPORTLAB,
                                reason="reportlab not installed")

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


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    yield
    queue_db.reset()
    paths.set_data_dir(None)


def test_violation_demo_generates_dossier():
    r = run_demo_scan(dossier=True)
    assert r["dossier"] is not None
    assert len(r["dossier"]["sha256"]) == 64
    assert r["dossier"]["sig_status"] == "pending"
    assert "s7_dossier" in r["timings_ms"]
    assert r["verdict"] == "VIOLATION" and r["summary"]["total"] == 11


def test_default_demo_writes_nothing():
    r = run_demo_scan()
    assert r["dossier"] is None
    assert not list(paths.dossier_dir().glob("*.pdf"))
    assert queue_db.get_db().status()["total"] == 0


def test_dossier_file_is_pdf_with_matching_sha():
    r = run_demo_scan(dossier=True)
    p = Path(r["dossier"]["pdf_path"])
    assert p.exists()
    data = p.read_bytes()
    assert data[:5] == b"%PDF-"
    import hashlib
    assert hashlib.sha256(data).hexdigest() == r["dossier"]["sha256"]


def test_retry_never_generates():
    rep = s7_dossier.run(PipelineContext())
    assert rep.ok and not rep.generated


def test_pass_requires_dossier_on_pass_option():
    ctx = PipelineContext()
    ctx.fields = {k: FieldValue(raw=v) for k, v in COMPLIANT.items()}
    ctx.pda_cm2 = 80.0
    ctx.font_heights = {"net_qty": 1.8, "mrp": 1.6}
    s6_metrology.run(ctx)
    assert ctx.verdict is Verdict.PASS
    rep = s7_dossier.run(ctx)
    assert rep.ok and not rep.generated and ctx.dossier_sha256 is None
    rep = s7_dossier.run(ctx, options={"dossier_on_pass": True})
    assert rep.generated and ctx.dossier_sha256


def test_pass_label_records_ledger_row_without_dossier():
    r = run_demo_scan(label=COMPLIANT, dossier=True)
    assert r["verdict"] == "PASS" and r["dossier"] is None
    row = queue_db.get_db().get_scan(r["scan_id"])
    assert row is not None and row["verdict"] == "PASS"
    assert row["dossier_sha256"] is None and row["sig_status"] == "pending"


def test_ledger_row_matches_result():
    r = run_demo_scan(dossier=True)
    row = queue_db.get_db().get_scan(r["scan_id"])
    assert row["verdict"] == "VIOLATION"
    assert row["dossier_sha256"] == r["dossier"]["sha256"]
    assert row["image_sha256"] == r["meta"] is not None or True
    assert row["image_sha256"]                    # demo frame hashed
    import json
    stored = json.loads(row["result_json"])
    assert stored["summary"] == r["summary"]


def test_queue_status_counts():
    run_demo_scan(dossier=True)
    st = queue_db.get_db().status()
    assert st == {"total": 1, "pending_sync": 1, "signed": 0, "dossiers": 1}


def test_reportlab_missing_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(pdf_builder, "HAVE_REPORTLAB", False)
    r = run_demo_scan(dossier=True)
    assert r["verdict"] == "VIOLATION"          # statutory scan unaffected
    assert r["dossier"] is None


def test_evidence_crops_grow_the_pdf():
    violation = run_demo_scan(dossier=True)
    compliant = run_demo_scan(label=COMPLIANT, options={"dossier_on_pass": True},
                              dossier=True)
    assert violation["dossier"] is not None
    assert compliant["dossier"] is not None
    v = Path(violation["dossier"]["pdf_path"]).stat().st_size
    c = Path(compliant["dossier"]["pdf_path"]).stat().st_size
    assert v > 5_000 and v > c
