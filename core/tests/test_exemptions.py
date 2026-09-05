from netra_core.rules.exemptions import assess_exemption


class TestSmallPackages:
    def test_10g_inclusive(self):
        assert assess_exemption(10, "g").exempt

    def test_just_over_10g_not_exempt(self):
        assert not assess_exemption("10.1", "g").exempt

    def test_mg_converted(self):
        assert assess_exemption(10, "mg").exempt

    def test_10ml(self):
        assert assess_exemption(10, "ml").exempt

    def test_tobacco_family_denied(self):
        for commodity in ["Bidi", "Chewing Tobacco", "Pan Masala Supreme"]:
            assert not assess_exemption(8, "g", commodity).exempt


class TestBulkPackages:
    def test_26kg_rice_exempt(self):
        assert assess_exemption(26, "kg").exempt

    def test_25kg_not_exempt(self):
        assert not assess_exemption(25, "kg").exempt

    def test_cement_30kg_not_exempt(self):
        assert not assess_exemption(30, "kg", "Portland Cement").exempt

    def test_cement_50kg_not_exempt(self):
        assert not assess_exemption(50, "kg", "cement").exempt

    def test_cement_55kg_exempt(self):
        assert assess_exemption("55.5", "kg", "cement").exempt

    def test_fertilizer_50kg_not_exempt(self):
        assert not assess_exemption(50, "kg", "Urea Fertilizer").exempt

    def test_30l_exempt(self):
        assert assess_exemption(30, "L").exempt


class TestContextualExemptions:
    def test_institutional(self):
        assert assess_exemption(500, "g", institutional=True).exempt

    def test_fast_food(self):
        assert assess_exemption(250, "g", fast_food=True).exempt


def test_count_packages_never_quantity_exempt():
    assert not assess_exemption(6, "piece").exempt
