"""Text -> typed-value parsers (Stage 5 feeds these; Stage 6 & tests use them).

Conventions:
- Money/quantities are Decimal — never floats near statutory arithmetic.
- Units are canonicalised (ltr->L, pcs->piece, nos->N ...) so the rule engine
  compares symbols, not spellings. Prohibited-syntax detection is a separate
  concern (rules.si_units) operating on the raw text.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


# ------------------------------------------------------------------ normalise
def normalize(text: str) -> str:
    """NFC-fold, superscripts -> digits, squash whitespace."""
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    for src, dst in (("²", "2"), ("³", "3"), ("₨", "Rs"), ("\u00a0", " ")):
        t = t.replace(src, dst)
    return re.sub(r"\s+", " ", t).strip()


def to_decimal(x) -> Decimal:
    """str/int/Decimal/float -> Decimal (floats via str to dodge binary noise)."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int):
        return Decimal(x)
    return Decimal(str(x).strip())


def _num(s: str) -> Decimal:
    """'1,25,000' -> 125000 ; '50.00' -> 50.00. Indian convention: commas are
    grouping separators, the dot is the decimal point."""
    s = s.replace(",", "")
    parts = s.split(".")
    if len(parts) > 2:                       # stray multiple dots
        s = "".join(parts[:-1]) + "." + parts[-1]
    else:
        s = ".".join(parts)
    return Decimal(s)


# ----------------------------------------------------------------- quantities
_UNIT_CANON = {
    "mg": "mg", "g": "g", "gm": "g", "gms": "g", "grm": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
    "l": "L", "lt": "L", "ltr": "L", "litre": "L", "litres": "L", "liter": "L", "liters": "L",
    "ml": "ml", "cl": "cl",
    "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml",
    "mm": "mm", "cm": "cm", "m": "m", "cm2": "cm2", "m2": "m2",
    "n": "N", "nos": "N",
    "u": "U", "unit": "U", "units": "U",
    "pcs": "piece", "pc": "piece", "piece": "piece", "pieces": "piece",
    "pair": "pair", "set": "set",
}

_QTY_RE = re.compile(
    r"([0-9]+(?:[.,][0-9]+)*)\s*"
    r"(millilitres?|milliliters?|litres?|liters?|ltr?|kilograms?|kilos?|kgs?|"
    r"gms?|grm|grams?|gm|g|mg|cl|ml|cm2|cm|mm|m2|m|nos|n|units?|u|"
    r"pcs|pieces?|pc|pair|set)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit: str        # canonical
    raw_unit: str    # exactly as printed


def parse_quantity(text: str) -> Optional[Quantity]:
    m = _QTY_RE.search(normalize(text))
    if not m:
        return None
    raw_unit = m.group(2).lower()
    return Quantity(_num(m.group(1)), _UNIT_CANON.get(raw_unit, raw_unit), raw_unit)


# ---------------------------------------------------------------------- money
_MONEY_RE = re.compile(
    r"(?<![a-z0-9])(?:₹|rs\.?|inr)\s*([0-9]+(?:[.,][0-9]+)*)",
    re.IGNORECASE,
)


def parse_money(text: str) -> Optional[Decimal]:
    m = _MONEY_RE.search(normalize(text))
    return _num(m.group(1)) if m else None


# ------------------------------------------------------------------------ USP
_USP_RE = re.compile(
    r"([0-9]+(?:[.,][0-9]+)*)\s*(?:/|per\s*)\s*([a-z]+[0-9]?)\b",
    re.IGNORECASE,
)


def parse_usp(text: str) -> Optional[Quantity]:
    m = _USP_RE.search(normalize(text))
    if not m:
        return None
    raw_unit = m.group(2).lower()
    return Quantity(_num(m.group(1)), _UNIT_CANON.get(raw_unit, raw_unit), raw_unit)


# ---------------------------------------------------------------------- dates
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

_DATE_RE = re.compile(
    r"([0-9]{1,2})\s*[/\-.]\s*([0-9]{4})"                 # MM/YYYY
    r"|([a-z]{3,9})\s*[\-,. ]{0,3}\s*([0-9]{4})",          # Month YYYY,
    re.IGNORECASE,
)


def parse_date(text: str) -> Optional[date]:
    """Rule 6(1)(d): MM/YYYY or Month YYYY -> date (day pinned to 1)."""
    m = _DATE_RE.search(normalize(text))
    if not m:
        return None
    if m.group(1) is not None:
        month, year = int(m.group(1)), int(m.group(2))
    else:
        month = _MONTHS.get(m.group(3).lower()[:3])
        year = int(m.group(4))
    if month is None or not 1 <= month <= 12:
        return None
    try:
        return date(year, month, 1)
    except ValueError:
        return None
