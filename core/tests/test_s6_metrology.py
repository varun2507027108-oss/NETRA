from netra_core.context import FieldValue, GlyphBox, PipelineContext, Verdict
from netra_core.stages import s6_metrology


def fv(raw, value=None, unit=None):
    return FieldValue(raw=raw, value=value, unit=unit)


GOOD_LABEL = {
    "product_name":  fv("Instant Masala Noodles"),
    "net_qty":       fv("Net Quantity: 70 g", value="70", unit="g"),
    "mrp":           fv("MRP ₹ 14.00 (incl. of all taxes)", value="14.00"),
    "usp":           fv("Unit Sale Price ₹ 0.20 / g"),
    "mfg_date":      fv("MFG 08/2026"),
    "mfg_address":   fv("Mfd. by: Tasty Foods Ltd., Plot 21, Goa 403001"),
    "origin":        fv("Made in India"),
    "consumer_care": fv("Consumer Care: Tasty Foods, Mumbai 400050, "
                        "Tel: 1800-123-4567, care@tasty.in"),
}


def build(fields):
    ctx = PipelineContext()
    ctx.fields.update(fields)
    return ctx


def failed_rules(ctx):
    return {c.rule for c in ctx.failed_checks}


def test_fully_compliant_pass():
    ctx = build(GOOD_LABEL)
    s6_metrology.run(ctx)
    assert ctx.verdict is Verdict.PASS
    assert failed_rules(ctx) == set()


def test_gms_is_double_violation():
    fields = dict(GOOD_LABEL)
    fields["net_qty"] = fv("Net Quantity: 200 gms", value="200", unit="g")
    ctx = build(fields)
    s6_metrology.run(ctx)
    assert {"13", "6(1)(c)"} <= failed_rules(ctx)
    assert ctx.verdict is Verdict.VIOLATION


def test_mrp_phrase_missing():
    fields = dict(GOOD_LABEL)
    fields["mrp"] = fv("MRP ₹ 14.00", value="14.00")
    ctx = build(fields)
    s6_metrology.run(ctx)
    assert "6(1)(e)" in failed_rules(ctx)


def test_usp_math_violation():
    fields = dict(GOOD_LABEL)
    fields["usp"] = fv("Unit Sale Price ₹ 0.35 / g")
    ctx = build(fields)
    s6_metrology.run(ctx)
    assert "6(11)" in failed_rules(ctx)


def test_missing_mrp_field():
    fields = {k: v for k, v in GOOD_LABEL.items() if k != "mrp"}
    ctx = build(fields)
    s6_metrology.run(ctx)
    assert "6(1)(e)" in failed_rules(ctx)
    usp = [c for c in ctx.checks if c.rule == "6(11)"]
    assert usp[0].status.value == "NA"


def test_rule26_exempt_package_passes_with_na():
    fields = dict(GOOD_LABEL)
    fields["net_qty"] = fv("Net Quantity: 8 g", value="8", unit="g")
    ctx = build(fields)
    s6_metrology.run(ctx)
    assert ctx.verdict is Verdict.PASS
    assert {c.rule for c in ctx.checks} == {"26"}
    assert all(c.status.value == "NA" for c in ctx.checks)


def test_institutional_option_exempts():
    ctx = build(GOOD_LABEL)
    s6_metrology.run(ctx, options={"institutional": True})
    assert ctx.verdict is Verdict.PASS
    assert {c.rule for c in ctx.checks} == {"26"}


def test_no_fields_marks_retry():
    ctx = PipelineContext()
    s6_metrology.run(ctx)
    assert ctx.verdict is Verdict.RETRY
    assert ctx.stages[-1].stage == "s6_metrology" and not ctx.stages[-1].ok


def test_font_height_violation():
    ctx = build(GOOD_LABEL)
    ctx.pda_cm2 = 100.0                       # band 2 -> 1.5 mm minimum
    ctx.font_heights = {"net_qty": 1.8, "mrp": 1.2}
    s6_metrology.run(ctx)
    failed = [c for c in ctx.checks
              if c.rule == "7" and c.status.value == "FAIL"]
    assert len(failed) == 1 and "mrp" in failed[0].message.lower()


def test_glyph_aspect_violation():
    ctx = build(GOOD_LABEL)
    ctx.glyphs = [GlyphBox("M", 3.0, 0.5, "mrp"), GlyphBox("5", 3.0, 1.0, "mrp")]
    s6_metrology.run(ctx)
    assert "7(3)" in failed_rules(ctx)


def test_glyph_aspect_narrow_exempt():
    ctx = build(GOOD_LABEL)
    ctx.glyphs = [GlyphBox("i", 3.0, 0.1, "product_name")]
    s6_metrology.run(ctx)
    assert "7(3)" not in failed_rules(ctx)


def test_prc_origin_violation():
    fields = dict(GOOD_LABEL)
    fields["origin"] = fv("Made in PRC")
    ctx = build(fields)
    s6_metrology.run(ctx)
    assert "6(1)(aa)" in failed_rules(ctx)


def test_imported_missing_origin_fails():
    fields = {k: v for k, v in GOOD_LABEL.items() if k != "origin"}
    fields["mfg_address"] = fv("Imported by: Global Foods, Mumbai 400001")
    ctx = build(fields)
    s6_metrology.run(ctx)
    assert "6(1)(aa)" in failed_rules(ctx)


def test_stage_timing_recorded():
    ctx = build(GOOD_LABEL)
    s6_metrology.run(ctx)
    assert ctx.stages[-1].duration_ms >= 0.0
