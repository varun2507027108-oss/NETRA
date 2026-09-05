from netra_core.rules.declarations import (
    check_address, check_consumer_care, check_country_of_origin,
    check_mfg_date, check_mrp, check_net_quantity, check_presence,
    extract_pin, looks_imported,
)


class TestMRP:
    def test_compliant_with_symbol(self):
        assert check_mrp("MRP ₹ 50.00 (incl. of all taxes)").ok

    def test_compliant_with_words(self):
        assert check_mrp("Maximum Retail Price Rs. 99 inclusive of all taxes").ok

    def test_ocr_spacing_variant(self):
        assert check_mrp("MRP ₹ 99.50 incl.of all taxes").ok

    def test_missing_tax_phrase(self):
        r = check_mrp("MRP ₹ 50.00")
        assert not r.ok and "inclusive of all taxes" in r.detail

    def test_missing_amount(self):
        r = check_mrp("MRP incl. of all taxes")
        assert not r.ok and "rupee" in r.detail

    def test_empty(self):
        assert not check_mrp("").ok


class TestPin:
    def test_marker(self):
        assert extract_pin("Pin Code: 110001") == "110001"

    def test_bare_at_tail(self):
        assert extract_pin("Andheri East, Mumbai 400093") == "400093"

    def test_spaced_bare(self):
        assert extract_pin("New Delhi 110 001") == "110001"

    def test_phone_is_not_pin(self):
        assert extract_pin("Tel: 1800 123 4567, Mumbai 400093") == "400093"

    def test_long_numbers_ignored(self):
        assert extract_pin("Call 9820012345") is None

    def test_absent(self):
        assert extract_pin("hello world") is None


class TestAddress:
    def test_compliant(self):
        r = check_address(
            "Mfd. by: HUL Ltd., Unilever House, Andheri East, Mumbai 400093")
        assert r.ok and r.pin == "400093"

    def test_missing_pin(self):
        r = check_address("Mfd by XYZ Foods, Industrial Area, Pune")
        assert not r.ok and "PIN" in r.detail

    def test_packer_without_manufacturer_flagged(self):
        r = check_address("Packed by: Sweet Foods Pvt Ltd, Nashik 422001")
        assert not r.ok and "manufacturer" in r.detail.lower()

    def test_packer_with_manufacturer_ok(self):
        r = check_address(
            "Manufactured by A Foods, packed by B Packs, Delhi 110001")
        assert r.ok


class TestOrigin:
    def test_made_in_india(self):
        assert check_country_of_origin("Made in India").ok

    def test_phrase_form(self):
        r = check_country_of_origin("Country of Origin: China")
        assert r.ok and r.origin == "china"

    def test_prc_is_ambiguous(self):
        r = check_country_of_origin("Made in PRC")
        assert not r.ok and "ambiguous" in r.detail.lower()

    def test_product_of_usa(self):
        assert check_country_of_origin("Product of USA").ok

    def test_pr_china_explicit_ok(self):
        assert check_country_of_origin("Made in P.R. China").ok

    def test_unrecognized_origin(self):
        assert not check_country_of_origin("Made in Dubai").ok

    def test_missing_on_imported(self):
        r = check_country_of_origin("", imported_hint=True)
        assert not r.ok

    def test_missing_on_domestic_is_na(self):
        assert check_country_of_origin("").ok is None


class TestImportHint:
    def test_looks_imported(self):
        assert looks_imported("Imported by: Global Traders, Mumbai 400001")
        assert not looks_imported("Mfd. by XYZ Foods, Pune")


class TestMfgDate:
    def test_mm_yyyy(self):
        assert check_mfg_date("MFG 03/2026").ok

    def test_month_name(self):
        assert check_mfg_date("AUG 2026").ok

    def test_dd_mm_yyyy(self):
        r = check_mfg_date("15/08/2025")
        assert r.ok and "08/2025" in r.detail

    def test_mm_dd_yyyy_disambiguated(self):
        assert check_mfg_date("03/13/2026").ok

    def test_dd_mm_yyyy_default_when_ambiguous(self):
        assert check_mfg_date("03/04/2026").ok

    def test_garbage_rejected(self):
        assert not check_mfg_date("Best taste before").ok

    def test_empty(self):
        assert not check_mfg_date("").ok


class TestConsumerCare:
    def test_complete(self):
        r = check_consumer_care(
            "Consumer Care: ABC Ltd, 2nd Floor, Linking Road, Mumbai 400050, "
            "Tel: 1800-123-4567, care@abc.in")
        assert r.ok

    def test_missing_email(self):
        r = check_consumer_care(
            "Consumer Care: ABC Ltd, Mumbai 400050, Tel: 9876543210")
        assert not r.ok and "email" in r.detail

    def test_missing_phone(self):
        r = check_consumer_care("ABC Ltd, Mumbai 400050, care@abc.in")
        assert not r.ok and "helpline" in r.detail


class TestNetQuantity:
    def test_grams(self):
        assert check_net_quantity("Net Quantity: 200 g").ok

    def test_millilitres(self):
        assert check_net_quantity("350 mL").ok

    def test_prohibited_unit(self):
        assert not check_net_quantity("Net Qty 200 gms").ok

    def test_nos_tolerated(self):
        r = check_net_quantity("Contains 6 Nos")
        assert r.ok and "printed 'nos'" in r.detail

    def test_not_decodable(self):
        assert not check_net_quantity("Net Quantity: assorted").ok


class TestPresence:
    def test_presence(self):
        assert check_presence("Instant Noodles", "common/generic name").ok
        assert not check_presence("123", "common/generic name").ok
        assert not check_presence("", "common/generic name").ok
