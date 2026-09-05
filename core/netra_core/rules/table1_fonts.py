"""Rule 7 — Principal Display Area, Table-I font heights, glyph aspect.

Statutory source: LMPC (Packaged Commodities) Rules 2011, Rule 7 and
Table-I as amended by G.S.R. 629(E).

NOTE: values mirror the SIH26034 spec document. Before final submission,
diff these five rows against the gazette text of G.S.R. 629(E) — the
blown/molded column is the one to double-check. It is centralised here so
a correction is a one-line change.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FontBand:
    pda_max_cm2: Optional[float]    # None -> unbounded
    min_height_mm: float            # normal print
    min_height_blown_mm: float      # blown / formed / molded / embossed


TABLE_I: tuple = (
    FontBand(50.0,    1.0, 1.5),
    FontBand(100.0,   1.5, 3.0),
    FontBand(500.0,   2.5, 4.0),
    FontBand(2500.0,  4.0, 6.0),
    FontBand(None,    6.0, 6.0),
)


def band_index(pda_cm2: float) -> int:
    """1-based Table-I serial number for a given PDA (band bound is inclusive)."""
    if pda_cm2 <= 0:
        raise ValueError(f"PDA must be positive, got {pda_cm2}")
    for i, band in enumerate(TABLE_I, start=1):
        if band.pda_max_cm2 is None or pda_cm2 <= band.pda_max_cm2:
            return i
    raise AssertionError("unreachable")


def min_font_height_mm(pda_cm2: float, blown: bool = False) -> float:
    band = TABLE_I[band_index(pda_cm2) - 1]
    return band.min_height_blown_mm if blown else band.min_height_mm


def font_height_ok(pda_cm2, measured_mm, blown=False, tol_mm=0.0):
    """Returns (ok, required_mm). Stage 6 passes FONT_TOL_MM as tol_mm."""
    required = min_font_height_mm(pda_cm2, blown)
    return measured_mm >= required - tol_mm, required


# ---- Rule 7(4): PDA computation -------------------------------------------
def pda_rectangular_cm2(height_cm: float, width_cm: float) -> float:
    """One entire principal display side (excludes tops/bottoms/flanges)."""
    return float(height_cm * width_cm)


def pda_cylindrical_cm2(height_cm: float, diameter_cm: float) -> float:
    """0.40 x H x (pi x D)."""
    return 0.40 * float(height_cm) * math.pi * float(diameter_cm)


def pda_other_cm2(total_surface_cm2: float) -> float:
    """40% of total surface area / designated principal display panel."""
    return 0.40 * float(total_surface_cm2)


# ---- Rule 7(3): character width --------------------------------------------
NARROW_GLYPHS = frozenset({"1", "i", "I", "l"})


def glyph_min_width_mm(height_mm: float, glyph: str) -> float:
    """Width >= height/3, except for 1, i, I, l."""
    return 0.0 if glyph in NARROW_GLYPHS else height_mm / 3.0


def glyph_aspect_ok(height_mm: float, width_mm: float, glyph: str) -> bool:
    return width_mm >= glyph_min_width_mm(height_mm, glyph) - 1e-9
