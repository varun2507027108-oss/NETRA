from decimal import Decimal

from netra_core.context import PipelineContext
from netra_core.stages import s5_field_extract
from netra_core.stages.s5_field_extract import extract_fields


def tok(x, y, w, h, text, conf=0.97):
    from netra_core.context import BBox, OCRToken
    return OCRToken(text=text, bbox=BBox(x, y, w, h), conf=conf,
                    engine="mlkit", lang="en")


class TestInlineValues:
    def test_mrp_single_token(self):
        f = extract_fields([tok(100, 100, 400, 40,
                                "MRP ₹ 50.00 (incl. of all taxes)")])
        assert f["mrp"].value == Decimal("50.00")
        assert "(incl. of all taxes)" in f["mrp"].raw

    def test_net_qty_single_token(self):
        f = extract_fields([tok(100, 100, 200, 30, "Net Quantity: 70 g")])
        assert f["net_qty"].value == Decimal("70")
        assert f["net_qty"].unit == "g"


class TestSameLineExtraction:
    def test_split_anchor_value(self):
        f = extract_fields([
            tok(120, 340, 150, 30, "Net Quantity:"),
            tok(280, 340, 80, 30, "70 g"),
        ])
        assert f["net_qty"].raw == "Net Quantity: 70 g"
        assert f["net_qty"].value == Decimal("70")
        assert f["net_qty"].bbox.to_list() == [120, 340, 240, 30]

    def test_mrp_three_tokens_including_tax_phrase(self):
        f = extract_fields([
            tok(120, 388, 60, 40, "MRP"),
            tok(190, 388, 110, 40, "₹ 50.00"),
            tok(310, 388, 220, 40, "(incl. of all taxes)"),
        ])
        assert f["mrp"].raw == "MRP ₹ 50.00 (incl. of all taxes)"
        assert f["mrp"].value == Decimal("50.00")

    def test_mrp_best_effort_without_phrase(self):
        # no tax phrase anywhere: money still extracts so s6 can flag the phrase
        f = extract_fields([
            tok(120, 388, 60, 40, "MRP"),
            tok(190, 388, 110, 40, "₹ 14.00"),
        ])
        assert f["mrp"].raw == "MRP ₹ 14.00"

    def test_usp_split(self):
        f = extract_fields([
            tok(120, 432, 160, 30, "Unit Sale Price"),
            tok(285, 432, 130, 30, "₹ 0.25 / g"),
        ])
        assert f["usp"].value == Decimal("0.25")
        assert f["usp"].unit == "g"


class TestWrappedValues:
    def test_value_on_line_below_anchor(self):
        f = extract_fields([
            tok(100, 200, 150, 30, "Net Quantity:"),
            tok(100, 235, 80, 30, "200 g"),
        ])
        assert f["net_qty"].value == Decimal("200")
        assert f["net_qty"].unit == "g"


class TestParagraphs:
    def test_address_two_lines(self):
        f = extract_fields([
            tok(40, 600, 300, 26, "Mfd. by: Global Foods,"),
            tok(40, 630, 180, 26, "Mumbai 400093"),
        ])
        assert "400093" in f["mfg_address"].raw
        assert f["mfg_address"].value is None

    def test_paragraph_stops_at_foreign_anchor(self):
        f = extract_fields([
            tok(40, 600, 300, 26, "Mfd. by: Global Foods,"),
            tok(40, 630, 180, 26, "Mumbai 400093"),
            tok(40, 660, 300, 26, "Consumer Care: X Ltd,"),
            tok(40, 690, 150, 26, "Tel: 1800-123-4567"),
        ])
        assert "Mumbai" in f["mfg_address"].raw
        assert "Consumer" not in f["mfg_address"].raw
        assert "Tel" in f["consumer_care"].raw

    def test_paragraph_gap_limit(self):
        f = extract_fields([
            tok(40, 600, 200, 26, "Mfd. by: X,"),
            tok(40, 700, 150, 26, "Pune 411001"),   # 74px gap -> separate block
        ])
        assert f["mfg_address"].raw == "Mfd. by: X,"


class TestFallbacks:
    def test_usp_without_anchor(self):
        f = extract_fields([tok(100, 100, 150, 30, "₹ 0.25 / g")])
        assert f["usp"].value == Decimal("0.25")
        assert f["usp"].unit == "g"

    def test_no_tokens_returns_empty(self):
        assert extract_fields([]) == {}


class TestProductName:
    def test_largest_unconsumed_token_wins(self):
        f = extract_fields([
            tok(200, 60, 300, 60, "Instant Noodles"),
            tok(120, 340, 150, 30, "Net Quantity:"),
            tok(280, 340, 80, 30, "70 g"),
        ])
        assert f["product_name"].raw == "Instant Noodles"
        assert f["net_qty"].value == Decimal("70")

    def test_anchor_tokens_are_never_product_name(self):
        f = extract_fields([
            tok(50, 50, 200, 60, "MRP ₹ 99"),
            tok(50, 150, 200, 40, "Noodles"),
        ])
        assert f["product_name"].raw == "Noodles"
        assert f["mrp"].value == Decimal("99")


class TestDeterminism:
    def test_multiple_anchors_second_wins(self):
        f = extract_fields([
            tok(50, 100, 60, 30, "MRP"),              # orphan anchor, no value
            tok(50, 300, 60, 30, "MRP"),
            tok(120, 300, 110, 30, "₹ 99.00"),
        ])
        assert f["mrp"].value == Decimal("99.00")

    def test_repeat_runs_identical(self):
        toks = [
            tok(120, 340, 150, 30, "Net Quantity:"),
            tok(280, 340, 80, 30, "70 g"),
            tok(120, 388, 60, 40, "MRP"),
            tok(190, 388, 110, 40, "₹ 14.00"),
        ]
        assert extract_fields(toks) == extract_fields(toks)


class TestStageIntegration:
    def test_run_populates_fields_and_font_heights(self):
        ctx = PipelineContext()
        ctx.tokens = [
            tok(120, 340, 150, 30, "Net Quantity:"),
            tok(280, 340, 80, 30, "70 g"),
        ]
        ctx.mm_per_px = 0.04
        fields = s5_field_extract.run(ctx)
        assert "net_qty" in fields
        assert ctx.font_heights["net_qty"] == 1.2
        assert ctx.stages[-1].stage == "s5_field_extract"
        assert ctx.stages[-1].ok

    def test_run_with_no_tokens_not_ok(self):
        ctx = PipelineContext()
        ctx.tokens = []
        s5_field_extract.run(ctx)
        assert not ctx.stages[-1].ok
        assert ctx.fields == {}
