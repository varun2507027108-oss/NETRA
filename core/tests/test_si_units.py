from decimal import Decimal

from netra_core.rules.parsers import (
    parse_date, parse_money, parse_money_lenient, parse_quantity, parse_usp,
)
from netra_core.rules.si_units import (
    find_prohibited_units, is_permitted, unit_syntax_ok,
)


def test_finds_each_prohibited_token():
    for bad in ["500 gms", "net 1 kilo", "2 kgs", "1 ltr", "5 cc",
                "10 pkts", "2 doz", "1 cu.cm", "1 cu cm"]:
        assert find_prohibited_units(bad), bad


def test_clean_text_has_no_hits():
    for ok in ["Net Quantity 500 g", "350 mL", "1 kg", "25 cm2",
               "MRP ₹ 50.00 incl. of all taxes", "kilometre marker"]:
        assert unit_syntax_ok(ok), ok


def test_hit_carries_suggestion_and_span():
    hits = find_prohibited_units("Net Qty 500 gms")
    assert hits[0].token == "gms" and hits[0].suggestion == "g"
    assert "Net Qty 500 gms"[hits[0].start:hits[0].end] == "gms"


def test_is_permitted():
    assert is_permitted("g") and is_permitted("mL") and is_permitted("kg")
    assert not is_permitted("gms") and not is_permitted("gm")


class TestParseQuantity:
    def test_basic(self):
        q = parse_quantity("Net Quantity: 200 g")
        assert (q.value, q.unit) == (Decimal("200"), "g")

    def test_no_space(self):
        assert parse_quantity("350mL").unit == "ml"

    def test_variants_canonicalised(self):
        assert parse_quantity("1 kilo").unit == "kg"
        assert parse_quantity("500 ltr").unit == "L"
        assert parse_quantity("10 pcs").unit == "piece"
        assert parse_quantity("6 Nos.").unit == "N"

    def test_indian_grouping(self):
        assert parse_quantity("1,000 g").value == Decimal("1000")

    def test_bare_litre_symbol(self):
        assert parse_quantity("1 L").unit == "L"
        assert parse_quantity("1 l").value == Decimal("1")
        assert parse_quantity("Net Quantity: 1 L").unit == "L"

    def test_none_when_absent(self):
        assert parse_quantity("MRP ₹ 50.00") is None
        assert parse_quantity("") is None


class TestParseMoney:
    def test_rupee_symbol(self):
        assert parse_money("MRP ₹ 50.00 (incl. of all taxes)") == Decimal("50.00")

    def test_rs(self):
        assert parse_money("MRP Rs. 99 (inclusive of all taxes)") == Decimal("99")

    def test_inr(self):
        assert parse_money("INR 125.50") == Decimal("125.50")

    def test_grouping(self):
        assert parse_money("₹ 1,25,000") == Decimal("125000")

    def test_none(self):
        assert parse_money("no price here") is None


class TestParseUSP:
    def test_slash_form(self):
        u = parse_usp("Unit Sale Price ₹ 0.25 / g")
        assert (u.value, u.unit) == (Decimal("0.25"), "g")

    def test_per_form(self):
        u = parse_usp("Rs. 33.33 per kg")
        assert (u.value, u.unit) == (Decimal("33.33"), "kg")


class TestParseDate:
    def test_mm_yyyy(self):
        assert parse_date("MFG 03/2026").isoformat()[:7] == "2026-03"

    def test_month_name(self):
        assert parse_date("AUG 2026").month == 8
        assert parse_date("March 2025").month == 3

    def test_dash_and_dot(self):
        assert parse_date("03-2026").month == 3
        assert parse_date("03.2026").month == 3

    def test_none(self):
        assert parse_date("hello world") is None
        assert parse_date("Best Before") is None


class TestParseMoneyLenient:
    def test_currency_marker_first(self):
        assert parse_money_lenient(
            "MRP ₹ 50.00 (incl. of all taxes)") == Decimal("50.00")

    def test_bare_after_mrp_keyword(self):
        assert parse_money_lenient(
            "MRP 14.00 (incl. of all taxes)") == Decimal("14.00")

    def test_bare_prefers_two_decimals(self):
        assert parse_money_lenient(
            "MRP 9 50.00 incl of all taxes") == Decimal("50.00")

    def test_no_context_no_bare(self):
        assert parse_money_lenient("Net Quantity: 70 g") is None

    def test_keyword_without_number_is_none(self):
        assert parse_money_lenient("MRP incl. of all taxes") is None
