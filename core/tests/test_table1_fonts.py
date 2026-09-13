import math

import pytest

from netra_core.rules.table1_fonts import (
    TABLE_I, band_index, compute_pda, glyph_aspect_ok, glyph_min_width_mm,
    min_font_height_mm, pda_cylindrical_cm2, pda_other_cm2, pda_rectangular_cm2,
)


@pytest.mark.parametrize("pda,serial", [
    (0.1, 1), (50.0, 1),          # band bound is inclusive
    (50.0001, 2), (100.0, 2),
    (100.01, 3), (500.0, 3),
    (500.01, 4), (2500.0, 4),
    (2500.01, 5), (10_000.0, 5),
])
def test_band_index(pda, serial):
    assert band_index(pda) == serial


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_band_index_rejects_nonpositive(bad):
    with pytest.raises(ValueError):
        band_index(bad)


@pytest.mark.parametrize("pda,blown,height", [
    (50.0, False, 1.0), (50.0, True, 1.5),
    (100.0, False, 1.5), (100.0, True, 3.0),
    (500.0, False, 2.5),
    (2500.0, False, 4.0), (2500.0, True, 6.0),
    (2500.01, False, 6.0), (2500.01, True, 6.0),
])
def test_min_font_height(pda, blown, height):
    assert min_font_height_mm(pda, blown) == height


def test_five_bands_present():
    assert len(TABLE_I) == 5


def test_pda_formulas():
    assert pda_rectangular_cm2(10, 6) == 60.0
    assert pda_cylindrical_cm2(10, 6) == pytest.approx(0.40 * 10 * math.pi * 6)
    assert pda_other_cm2(500) == pytest.approx(200.0)


class TestGlyphAspect:
    @pytest.mark.parametrize("glyph", ["1", "i", "I", "l"])
    def test_narrow_glyphs_exempt(self, glyph):
        assert glyph_aspect_ok(3.0, 0.01, glyph)
        assert glyph_min_width_mm(3.0, glyph) == 0.0

    def test_exactly_one_third_passes(self):
        assert glyph_aspect_ok(3.0, 1.0, "M")

    def test_below_one_third_fails(self):
        assert not glyph_aspect_ok(3.0, 0.99, "M")

    def test_numerals_enforced(self):
        assert glyph_aspect_ok(6.0, 2.0, "5")
        assert not glyph_aspect_ok(6.0, 1.9, "5")


def test_compute_pda_dispatch_parity():
    """Verify compute_pda reproduces every branch of the deleted _pda_from_options
    and s3_calibration dispatch across shapes, dimensions, and fallbacks."""
    # Cylindrical / bottle with h + d -> inspector-dims
    for shape in ("cylindrical", "bottle", "CYLINDRICAL", "Bottle"):
        pda, method = compute_pda(shape, {"package_height_cm": 15.0, "package_diameter_cm": 6.0})
        assert pda == pytest.approx(pda_cylindrical_cm2(15.0, 6.0))
        assert method == "inspector-dims"

    # Cylindrical with only h (missing d) -> None, ""
    assert compute_pda("cylindrical", {"package_height_cm": 15.0}) == (None, "")

    # Cylindrical with h + image_diameter_mm -> aruco-cylindrical
    pda, method = compute_pda("cylindrical", {"package_height_cm": 15.0}, image_diameter_mm=60.0)
    assert pda == pytest.approx(pda_cylindrical_cm2(15.0, 6.0))
    assert method == "aruco-cylindrical"

    # Rectangular / pouch with h + w -> inspector-dims
    for shape in ("rectangular", "pouch", "RECTANGULAR", "Pouch"):
        pda, method = compute_pda(shape, {"package_height_cm": 10.0, "package_width_cm": 5.0})
        assert pda == pytest.approx(50.0)
        assert method == "inspector-dims"

    # Rectangular missing w -> None, ""
    assert compute_pda("rectangular", {"package_height_cm": 10.0}) == (None, "")

    # Other shape with total_surface_cm2 -> inspector-dims (40%)
    pda, method = compute_pda("other", {"total_surface_cm2": 250.0})
    assert pda == pytest.approx(100.0)
    assert method == "inspector-dims"

    # Unknown / empty shape with h + w -> fallback to rectangular inspector-dims
    for shape in ("", None, "custom_box"):
        pda, method = compute_pda(shape, {"package_height_cm": 12.0, "package_width_cm": 8.0})
        assert pda == pytest.approx(96.0)
        assert method == "inspector-dims"

    # Unknown shape with total_surface_cm2 -> inspector-dims (40%)
    pda, method = compute_pda(None, {"total_surface_cm2": 150.0})
    assert pda == pytest.approx(60.0)
    assert method == "inspector-dims"

    # Empty options / missing all dimensions -> None, ""
    assert compute_pda("rectangular", {}) == (None, "")
    assert compute_pda(None, None) == (None, "")

    # Direct kwargs without options dict (backward compatibility with s3_calibration callers)
    assert compute_pda("rectangular", height_cm=10, width_cm=6) == (60.0, "inspector-dims")
    assert compute_pda("cylindrical", height_cm=10, diameter_cm=6)[1] == "inspector-dims"
    assert compute_pda("cylindrical", height_cm=10, image_diameter_mm=60.0)[1] == "aruco-cylindrical"
    assert compute_pda("other", total_surface_cm2=500) == (200.0, "inspector-dims")

