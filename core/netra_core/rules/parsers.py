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


_MRP_CONTEXT_RE = re.compile(
    r"\b(?:m\.?\s*r\.?\s*p\.?|max(?:imum)?\.?\s*retail\s*price)\b",
    re.IGNORECASE)
_BARE_AMOUNT_RE = re.compile(r"(?<![0-9.])[0-9]{1,6}(?:\.[0-9]{1,2})?(?![0-9])")


def parse_money_lenient(text: str) -> Optional[Decimal]:
    """MRP-context money parse.

    Currency-marked amounts always win (parse_money); otherwise, when an
    MRP/price keyword establishes pricing context, accept the first bare
    amount after it — preferring a two-decimal form when several are
    present (prices are printed Rs xx.xx; this guards against the rupee
    glyph decoding as a stray digit, e.g. 'MRP 9 50.00' -> 50.00). The
    keyword wording itself carries the rupee designation; the statutory
    PHRASE check ('incl. of all taxes') stays strict in
    declarations.check_mrp — the phrase is the legal trap, not the
    currency typography.
    """
    marked = parse_money(text)
    if marked is not None:
        return marked
    t = normalize(text)
    kw = _MRP_CONTEXT_RE.search(t)
    if kw is None:
        return None
    matches = list(_BARE_AMOUNT_RE.finditer(t[kw.end():]))
    if not matches:
        return None
    best = next((m for m in matches
                 if re.fullmatch(r"[0-9]+\.[0-9]{2}", m.group(0))),
                matches[0])
    return _num(best.group(0))


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

_YEAR_MIN, _YEAR_MAX = 1970, 2100

_DMY_RE = re.compile(       # 15/08/2025 or 03/13/2026
    r"(?<![0-9])([0-9]{1,2})\s*[/\-.]\s*([0-9]{1,2})\s*[/\-.]\s*([0-9]{4})(?![0-9])")
_MY_RE = re.compile(        # 03/2026
    r"(?<![0-9])([0-9]{1,2})\s*[/\-.]\s*([0-9]{4})(?![0-9])")
_MONY_RE = re.compile(      # AUG 2026 / March 2025
    r"([a-z]{3,9})\s*[\-,. ]{0,3}\s*([0-9]{4})(?![0-9])", re.IGNORECASE)


def parse_date(text: str) -> Optional[date]:
    """Rule 6(1)(d): month & year. Accepted forms, in try order:

    1. DD/MM/YYYY — a field > 12 must be the day (this also disambiguates
       MM/DD/YYYY); when both fit, the Indian DD/MM reading is the default.
       Day is pinned to 1: the statute demands month precision only.
    2. MM/YYYY.
    3. Month YYYY ('AUG 2026', 'March 2025', 'Sept 2026').

    Rejected: reversed YYYY/MM, missing year, implausible years
    (< 1970 or > 2100), month words that don't decode.
    """
    t = normalize(text)
    m = _DMY_RE.search(t)
    if m:
        a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and b <= 12:
            month = b                      # first field must be the day
        elif b > 12 and a <= 12:
            month = a                      # second field must be the day
        else:
            month = b                      # Indian DD/MM default
    else:
        m = _MY_RE.search(t)
        if m:
            month, year = int(m.group(1)), int(m.group(2))
        else:
            m = _MONY_RE.search(t)
            if m is None:
                return None
            month = _MONTHS.get(m.group(1).lower()[:3])
            year = int(m.group(2))
            if month is None:
                return None
    if not (_YEAR_MIN <= year <= _YEAR_MAX and 1 <= month <= 12):
        return None
    return date(year, month, 1)
