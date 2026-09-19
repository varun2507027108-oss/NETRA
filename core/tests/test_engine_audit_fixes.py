"""Tests for Statutory Engine Remediation Round 1 (Audit Issues 1, 2, 3, 5, 6).

Covers:
  1. Area quantity units (m2, cm2) are outside Rule 6(11) USP mandate -> status NA (Issue 2).
  2. Rule 13 prohibited unit check is scoped to quantity/USP declarations, ignoring postal addresses (Issue 1).
  3. Rule 13 still fires on non-standard unit syntax in quantity declarations (Issue 1).
  4. FIELD_MFG_DATE extracts date with 'PKD.' anchor under Rule 6(1)(d) (Issue 3).
  5. FIELD_NET_QTY extracts volumetric declaration with 'Net Vol.' anchor under Rule 6(1)(c) (Issue 5).
  6. parse_money_lenient does not leak into unit-price (USP) value during bare MRP extraction (Issue 6).
  7. parse_money_lenient preserves the two-decimal OCR glyph-guard preference within bounded tail (Issue 6 glyph guard).
"""
from decimal import Decimal
import pytest

from netra_core import paths
from netra_core.bridge.schema import scan_tokens_request_from_dict
from netra_core.persistence import queue_db
from netra_core.pipeline import run_scan_tokens
from netra_core.rules.parsers import parse_money_lenient


@pytest.fixture(autouse=True)
def data_dir(tmp_path):
    paths.set_data_dir(tmp_path / "netra")
    queue_db.reset()
    yield
    queue_db.reset()
    paths.set_data_dir(None)


def _scan(token_items, **extra):
    tokens = []
    for i, item in enumerate(token_items):
        if isinstance(item, str):
            tokens.append({
                "text": item,
                "bbox": [10, 10 + i * 40, 300, 30],
                "conf": 0.95,
                "engine": "mlkit",
                "lang": "en",
            })
        elif isinstance(item, tuple):
            text, bbox = item
            tokens.append({
                "text": text,
                "bbox": bbox,
                "conf": 0.95,
                "engine": "mlkit",
                "lang": "en",
            })
        elif isinstance(item, dict):
            tokens.append(item)
    body = {"tokens": tokens}
    body.update(extra)
    req, err = scan_tokens_request_from_dict(body)
    assert err is None, err
    return run_scan_tokens(req)


def _check(res, rule_id):
    checks = [c for c in res.get("checks", []) if c.get("rule") == rule_id]
    return checks[0] if checks else None


def test_area_quantity_na_not_crash():
    """Area net quantities (e.g. 2.5 m2, 100 cm2) do not crash pipeline; Rule 6(11) returns NA."""
    res_m2 = _scan([
        "Net Qty: 2.5 m2",
        "MRP Rs 500.00 (incl. of all taxes)",
    ])
    assert res_m2["error"] is None
    c_m2 = _check(res_m2, "6(11)")
    assert c_m2 is not None
    assert c_m2["status"] == "NA"
    assert "area quantities are outside the USP mandate" in c_m2["message"]

    res_cm2 = _scan([
        "Net Qty: 100 cm2",
        "MRP Rs 50.00 (incl. of all taxes)",
    ])
    assert res_cm2["error"] is None
    c_cm2 = _check(res_cm2, "6(11)")
    assert c_cm2 is not None
    assert c_cm2["status"] == "NA"
    assert "area quantities are outside the USP mandate" in c_cm2["message"]


def test_rule13_ignores_addresses():
    """Rule 13 does not evaluate postal addresses or corporate names (e.g. 'GMS Industrial Area')."""
    res = _scan([
        "Mfd. by: Tasty Foods Ltd., Plot 12, GMS Industrial Area, Bangalore 560001",
        "Net Qty: 500 g",
        "MRP Rs 50.00 (incl. of all taxes)",
    ])
    assert res["error"] is None
    c13 = _check(res, "13")
    assert c13 is not None
    assert c13["status"] == "PASS"
    assert "No prohibited unit symbols" in c13["message"]


def test_rule13_fires_on_quantity():
    """Rule 13 strictly catches prohibited unit spellings in quantity declarations (e.g. 'gms')."""
    res = _scan([
        "Net Qty: 500 gms",
        "MRP Rs 50.00 (incl. of all taxes)",
    ])
    assert res["error"] is None
    c13 = _check(res, "13")
    assert c13 is not None
    assert c13["status"] == "FAIL"
    assert "Prohibited unit syntax 'gms'" in c13["message"]


def test_pkd_anchor():
    """FIELD_MFG_DATE anchor extracts manufacturing/packing date anchored by 'PKD.'."""
    res = _scan([
        "PKD. 10/2025",
        "Net Qty: 100 g",
        "MRP Rs 50.00 (incl. of all taxes)",
    ])
    assert res["error"] is None
    assert res["fields"].get("mfg_date") is not None
    c = _check(res, "6(1)(d)")
    assert c is not None
    assert c["status"] == "PASS"


def test_net_vol_anchor():
    """FIELD_NET_QTY anchor extracts volumetric quantity anchored by 'Net Vol.'."""
    res = _scan([
        "Net Vol. 500 ml",
        "MRP Rs 50.00 (incl. of all taxes)",
    ])
    assert res["error"] is None
    assert res["fields"].get("net_qty") is not None
    c = _check(res, "6(1)(c)")
    assert c is not None
    assert c["status"] == "PASS"


def test_money_lenient_no_usp_inversion():
    """parse_money_lenient does not scan past USP anchor into the unit-sale-price amount."""
    # Currency-marked variant
    assert parse_money_lenient("MRP Rs 100 (incl. of all taxes) USP 0.50 / g") == Decimal("100")
    # Bare amount variant with tax clause
    assert parse_money_lenient("MRP 100 (incl. of all taxes) USP 0.50 / g") == Decimal("100")
    # Bare amount variant directly followed by USP
    assert parse_money_lenient("MRP 100 USP 0.50 / g") == Decimal("100")


def test_money_lenient_glyph_guard():
    """parse_money_lenient preserves two-decimal preference for OCR rupee glyph misreads within bounded tail."""
    assert parse_money_lenient("MRP 9 50.00") == Decimal("50.00")
    assert parse_money_lenient("MRP 9 50.00 (incl. of all taxes)") == Decimal("50.00")
    assert parse_money_lenient("MRP 9 50.00 (incl. of all taxes) USP 0.50 / g") == Decimal("50.00")
