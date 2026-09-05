from netra_core.qa import golden


def entry(**kw):
    base = {"shape": "pouch", "dims_cm": {"height": 20.0, "width": 13.0},
            "fields": {"net_qty": "Net Quantity: 70 g",
                       "mrp": "MRP ₹ 14.00 (incl. of all taxes)"},
            "expect_fail": []}
    base.update(kw)
    return base


def result(failed=(), fields=None, verdict="VIOLATION", tokens=8):
    return {"verdict": verdict,
            "checks": [{"rule": r, "status": "FAIL"} for r in failed]
                      + [{"rule": "6(1)(b)", "status": "PASS"}],
            "fields": fields if fields is not None else {
                "net_qty": {"raw": "Net Quantity: 70 g"},
                "mrp": {"raw": "MRP Rs 14.00 (incl. of all taxes)"}},
            "quality": {"prompts": []},
            "ocr": {"tokens": [{}] * tokens}}


class TestBuildOptions:
    def test_flat(self):
        o = golden.build_options(entry())
        assert o["package_height_cm"] == 20.0
        assert o["package_width_cm"] == 13.0

    def test_cylindrical(self):
        o = golden.build_options(entry(
            shape="cylindrical", dims_cm={"height": 10.0, "diameter": 6.0}))
        assert o["package_diameter_cm"] == 6.0
        assert "package_width_cm" not in o

    def test_other_surface(self):
        o = golden.build_options(entry(shape="other",
                                       dims_cm={"total_surface": 500}))
        assert o["total_surface_cm2"] == 500.0

    def test_passthrough_options(self):
        o = golden.build_options(entry(options={"institutional": True}))
        assert o["institutional"] is True


class TestCompare:
    def test_all_green(self):
        oc = golden.compare_fixture(entry(), result(verdict="PASS"))
        assert oc["status"] == "ok"

    def test_currency_tolerance(self):
        oc = golden.compare_fixture(entry(), result(verdict="PASS"))
        assert "mrp" in oc["fields_ok"]          # ₹ <-> Rs treated equal

    def test_missing_fail_is_mismatch(self):
        oc = golden.compare_fixture(entry(expect_fail=["13"]),
                                    result(verdict="PASS"))
        assert oc["status"] == "mismatch" and oc["missing_fail"] == ["13"]

    def test_extra_fail_is_mismatch(self):
        oc = golden.compare_fixture(entry(), result(failed=["6(1)(e)"]))
        assert oc["extra_fail"] == ["6(1)(e)"]

    def test_field_missing(self):
        fields = {"net_qty": {"raw": "Net Quantity: 70 g"}}
        oc = golden.compare_fixture(entry(),
                                    result(fields=fields, failed=["6(1)(e)"]))
        assert "mrp" in oc["fields_missing"]

    def test_field_mismatch(self):
        fields = {"net_qty": {"raw": "Net Quantity: 70 g"},
                  "mrp": {"raw": "MRP Rs 14.00"}}
        oc = golden.compare_fixture(entry(),
                                    result(fields=fields, failed=["6(1)(e)"]))
        assert "mrp" in oc["fields_mismatch"]

    def test_retry_is_capture(self):
        oc = golden.compare_fixture(entry(), result(verdict="RETRY"))
        assert oc["status"] == "capture_retry"

    def test_inband_error_is_error(self):
        r = result(verdict="RETRY")
        r["error"] = {"code": "INTERNAL", "message": "boom"}
        oc = golden.compare_fixture(entry(), r)
        assert oc["status"] == "error"


class TestNormalize:
    def test_punctuation_case_currency(self):
        assert golden.normalize_for_compare(
            "MRP ₹ 14.00 (incl. of all taxes)") == \
            golden.normalize_for_compare("mrp rs. 14.00 incl of all taxes")


class TestValidate:
    def test_good_entry(self):
        assert golden.validate_entry("P01", entry()) == []

    def test_bad_shape(self):
        assert golden.validate_entry("P01", entry(shape="hexagonal"))

    def test_missing_dims_flagged(self):
        assert golden.validate_entry("P01", entry(dims_cm={}))


class TestSummarize:
    def test_counts_and_prf(self):
        outcomes = {
            "A": golden.compare_fixture(entry(expect_fail=["13"]),
                                        result(failed=["13"])),
            "B": golden.compare_fixture(entry(), result(verdict="PASS")),
            "C": golden.compare_fixture(entry(expect_fail=["13", "6(1)(e)"]),
                                        result(failed=["13"])),
            "D": golden.compare_fixture(entry(), result(verdict="RETRY")),
        }
        s = golden.summarize(outcomes)
        assert s["fixtures"] == 4 and s["ok"] == 2 and s["mismatch"] == 1
        assert s["capture_retry"] == ["D"]
        assert s["rule_tp"] == 2 and s["rule_fp"] == 0 and s["rule_fn"] == 1
        assert s["rule_precision"] == 1.0
        assert s["rule_recall"] == 2 / 3
        assert s["field_extraction_rate"] == 1.0
