from decimal import Decimal

import pytest

from netra_core.rules.usp import evaluate_usp


class TestReferenceUnitSelection:
    def test_below_1kg_uses_grams(self):
        r = evaluate_usp(mrp=50, net_qty=200, qty_unit="g")
        assert r.required_unit == "g" and r.expected == Decimal("0.25")

    def test_above_1kg_uses_kg(self):
        r = evaluate_usp(mrp=75, net_qty=1.5, qty_unit="kg")
        assert r.required_unit == "kg" and r.expected == Decimal("50.00")

    def test_below_1l_uses_ml(self):
        r = evaluate_usp(mrp=30, net_qty=750, qty_unit="ml")
        assert r.required_unit == "ml" and r.expected == Decimal("0.04")

    def test_length_uses_cm_below_1m(self):
        r = evaluate_usp(mrp=100, net_qty=50, qty_unit="cm")
        assert r.required_unit == "cm" and r.expected == Decimal("2.00")

    def test_length_uses_m_above_1m(self):
        r = evaluate_usp(mrp=100, net_qty=2, qty_unit="m")
        assert r.required_unit == "m" and r.expected == Decimal("50.00")

    def test_mg_input_converted(self):
        r = evaluate_usp(mrp=10, net_qty=500, qty_unit="mg")
        assert r.required_unit == "g" and r.expected == Decimal("20.00")

    def test_count_uses_piece(self):
        r = evaluate_usp(mrp=60, net_qty=6, qty_unit="piece")
        assert r.required_unit == "piece" and r.expected == Decimal("10.00")


class TestOneUnitExemption:
    @pytest.mark.parametrize("qty,unit", [(1, "kg"), (1, "L"), (1, "m"), (1, "piece")])
    def test_exactly_one_unit_is_exempt(self, qty, unit):
        r = evaluate_usp(mrp=100, net_qty=qty, qty_unit=unit)
        assert r.exempt and r.compliant and r.required_unit is None

    def test_1000g_is_one_kg_exempt(self):
        assert evaluate_usp(mrp=40, net_qty=1000, qty_unit="g").exempt


class TestTolerance:
    def test_exact_match(self):
        r = evaluate_usp(50, 200, "g", declared="0.25", declared_unit="g")
        assert r.compliant and r.math_ok and r.unit_ok

    def test_one_paisa_boundary_passes(self):
        r = evaluate_usp(50, 200, "g", declared="0.24", declared_unit="g")
        assert r.math_ok and r.compliant            # |delta| == 0.01 is a pass

    def test_two_paise_fails(self):
        assert not evaluate_usp(50, 200, "g", declared="0.23", declared_unit="g").compliant

    def test_rounded_repeating_decimal_passes(self):
        # 10 / 35 = 0.2857…; a statutory 2-dp declaration of 0.29 must pass
        r = evaluate_usp(10, 35, "g", declared="0.29", declared_unit="g")
        assert r.math_ok


class TestViolations:
    def test_wrong_reference_unit_fails_even_if_math_consistent(self):
        r = evaluate_usp(50, 200, "g", declared="250", declared_unit="kg")
        assert not r.unit_ok and not r.compliant

    def test_missing_usp_is_non_compliant(self):
        r = evaluate_usp(50, 200, "g")
        assert not r.exempt and not r.compliant
        assert "not declared" in r.detail

    def test_declared_without_unit_fails(self):
        r = evaluate_usp(50, 200, "g", declared="0.25", declared_unit="")
        assert not r.unit_ok


class TestGuards:
    @pytest.mark.parametrize("mrp,qty,unit",
                             [(0, 200, "g"), (-5, 200, "g"), (50, 0, "g"), (50, -1, "g")])
    def test_invalid_inputs_raise(self, mrp, qty, unit):
        with pytest.raises(ValueError):
            evaluate_usp(mrp, qty, unit)

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            evaluate_usp(50, 200, "furlong")
