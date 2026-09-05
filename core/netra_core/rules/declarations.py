"""Rule 6 declaration checks — presence, syntax, and statutory traps.

Pure stdlib. Stage 5 hands these functions the raw OCR text of each
statutory field; they return DeclarationResult verdicts that Stage 6
converts into Check entries with rule citations.

Machine-verifiable vs. manual: PIN presence, unit symbols, tax phrasing,
date syntax, phone/email formats are deterministic. "Complete address"
semantics and generic-vs-brand naming are checked only via their
machine-verifiable proxy; details flag the residual manual review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .parsers import normalize, parse_date, parse_money, parse_quantity
from .si_units import is_permitted

# ---- canonical field keys (single source of truth; bridge/schema.py mirrors) ----
FIELD_PRODUCT_NAME = "product_name"
FIELD_NET_QTY = "net_qty"
FIELD_MRP = "mrp"
FIELD_USP = "usp"
FIELD_MFG_DATE = "mfg_date"
FIELD_MFG_ADDRESS = "mfg_address"
FIELD_ORIGIN = "origin"
FIELD_CONSUMER_CARE = "consumer_care"

FIELD_LABELS = {
    FIELD_PRODUCT_NAME: "common/generic name",
    FIELD_NET_QTY: "net quantity",
    FIELD_MRP: "MRP",
    FIELD_USP: "unit sale price",
    FIELD_MFG_DATE: "date of manufacture",
    FIELD_MFG_ADDRESS: "manufacturer/packer details",
    FIELD_ORIGIN: "country of origin",
    FIELD_CONSUMER_CARE: "consumer care details",
}


@dataclass(frozen=True)
class DeclarationResult:
    ok: Optional[bool]        # None -> not applicable / manual review
    detail: str
    pin: Optional[str] = None
    origin: Optional[str] = None


# ---- Rule 6(1)(e): MRP -----------------------------------------------------
_MRP_KEYWORD_RE = re.compile(
    r"\b(?:m\.?r\.?p\.?|max(?:imum)?\.?\s*retail\s*price)\b", re.IGNORECASE)
_TAX_PHRASE_RE = re.compile(
    r"incl(?:usive)?\.?\s*(?:of\s+)?all\s+taxes?", re.IGNORECASE)


def check_mrp(text: str) -> DeclarationResult:
    t = normalize(text or "")
    if not t:
        return DeclarationResult(False, "MRP declaration not found.")
    missing = []
    if not _MRP_KEYWORD_RE.search(t):
        missing.append("'MRP' / 'Maximum Retail Price' wording")
    amount = parse_money(t)
    if amount is None:
        missing.append("rupee amount")
    if not _TAX_PHRASE_RE.search(t):
        missing.append("statutory phrase 'inclusive of all taxes'")
    if missing:
        return DeclarationResult(
            False, f"MRP non-compliant — missing {', '.join(missing)}.")
    return DeclarationResult(True, f"MRP Rs {amount} inclusive of all taxes.")


# ---- Rule 6(1)(a): address & PIN --------------------------------------------
_LONG_NUMBER_RE = re.compile(r"(?<![0-9])(?:[0-9][\-\s]?){6,}[0-9](?![0-9])")
_PIN_MARKER_RE = re.compile(
    r"\b(?:pin\s*code|pincode|pin|p\.?\s*o\.?)\s*[:\-]?\s*([1-9][0-9]{2})\s?([0-9]{3})\b",
    re.IGNORECASE)
_PIN_BARE_RE = re.compile(r"(?<![0-9])[1-9][0-9]{5}(?![0-9])")
_PIN_SPACED_RE = re.compile(r"(?<![0-9])[1-9][0-9]{2}\s[0-9]{3}(?![0-9])")


def extract_pin(text: str) -> Optional[str]:
    """6-digit PIN; masks phone/toll-free runs first so they can't pose as PINs."""
    t = _LONG_NUMBER_RE.sub(" ", normalize(text or ""))
    m = _PIN_MARKER_RE.search(t)
    if m:
        return m.group(1) + m.group(2)
    m = _PIN_BARE_RE.search(t)
    if m:
        return m.group(0)
    m = _PIN_SPACED_RE.search(t)
    if m:
        return m.group(0).replace(" ", "")
    return None


_MFR_RE = re.compile(
    r"\b(?:mfg\.?|mfd\.?|manufactur(?:er|ed|ing)|made\s+by)\b", re.IGNORECASE)
_PACKER_RE = re.compile(
    r"\bpack(?:er|ed|ing)\s+by\b|\bpackers?\b", re.IGNORECASE)
_MARKETER_RE = re.compile(r"\bmarket(?:er|ed|ing)\s+by\b", re.IGNORECASE)


def check_address(text: str) -> DeclarationResult:
    t = normalize(text or "")
    if not t:
        return DeclarationResult(
            False, "Manufacturer / packer / importer details not found.")
    pin = extract_pin(t)
    has_mfr = bool(_MFR_RE.search(t))
    third_party = bool(_PACKER_RE.search(t) or _MARKETER_RE.search(t))
    if third_party and not has_mfr:
        return DeclarationResult(
            False,
            "Packer / marketer is named without manufacturer details — "
            "Rule 6(1)(a) requires both when a third party packs the commodity.",
            pin=pin)
    if pin is None:
        return DeclarationResult(
            False,
            "Address present but no valid 6-digit PIN code found — Rule 6(1)(a) "
            "requires a complete postal address incl. PIN.")
    return DeclarationResult(
        True, f"Manufacturer/packer details with PIN {pin}.", pin=pin)


# ---- Rule 6(1)(aa): country of origin ----------------------------------------
COUNTRIES = frozenset({
    "india", "china", "people's republic of china", "taiwan", "hong kong",
    "macau", "macao", "japan", "korea", "south korea", "republic of korea",
    "thailand", "vietnam", "viet nam", "malaysia", "singapore", "indonesia",
    "philippines", "sri lanka", "nepal", "bhutan", "bangladesh", "pakistan",
    "maldives", "myanmar", "united states", "united states of america", "usa",
    "us", "united kingdom", "uk", "great britain", "england", "germany",
    "france", "italy", "spain", "portugal", "netherlands", "belgium",
    "switzerland", "austria", "denmark", "sweden", "norway", "finland",
    "poland", "greece", "ireland", "czech republic", "czechia", "hungary",
    "romania", "turkey", "turkiye", "russia", "ukraine", "israel",
    "saudi arabia", "uae", "united arab emirates", "qatar", "kuwait", "oman",
    "bahrain", "iran", "iraq", "egypt", "south africa", "nigeria", "kenya",
    "ghana", "ethiopia", "tanzania", "morocco", "australia", "new zealand",
    "canada", "mexico", "brazil", "argentina", "chile", "colombia", "peru",
})  # extensible — add as fixture data demands

AMBIGUOUS_ORIGINS = frozenset({
    "prc", "roc", "eu", "europe", "asia", "middle east", "foreign", "imported",
})


def _finder(words) -> re.Pattern:
    pattern = r"\b(" + "|".join(
        sorted((re.escape(w) for w in words), key=lambda w: (-len(w), w))
    ) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


_COUNTRY_FINDER = _finder(COUNTRIES)
_AMBIGUOUS_FINDER = _finder(AMBIGUOUS_ORIGINS)

_ORIGIN_PHRASE_RE = re.compile(
    r"\b(?:country\s+of\s+origin|origin|made\s+in|product\s+of|"
    r"manufactured\s+in|packed\s+in|assembled\s+in)\b\s*[:\-]?\s*"
    r"([a-z][a-z .&]{0,40})",
    re.IGNORECASE)
_IMPORT_HINT_RE = re.compile(r"\bimport(?:er|ed|ers|ing)?\b", re.IGNORECASE)


def looks_imported(*texts) -> bool:
    return any(_IMPORT_HINT_RE.search(normalize(t or "")) for t in texts)


def check_country_of_origin(text: str,
                            imported_hint: bool = False) -> DeclarationResult:
    t = normalize(text or "")
    if t:
        m = _ORIGIN_PHRASE_RE.search(t)
        tail = (m.group(1) if m else t).strip(" .,:;-&")
        country = _COUNTRY_FINDER.search(tail)
        if country:
            return DeclarationResult(
                True, f"Country of origin: {country.group(1)}.",
                origin=country.group(1).lower())
        ambiguous = _AMBIGUOUS_FINDER.search(tail)
        if ambiguous:
            return DeclarationResult(
                False,
                f"Ambiguous origin '{ambiguous.group(1)}' — Rule 6(1)(aa) requires "
                f"an explicit country (e.g., 'Made in PRC' must read 'Made in China').")
        return DeclarationResult(
            False, f"Origin text '{tail[:40]}' does not name a recognized country.")
    if imported_hint:
        return DeclarationResult(
            False,
            "Country of origin missing — mandatory on imported packages "
            "(Rule 6(1)(aa)).")
    return DeclarationResult(
        None,
        "Country of origin not found; mandatory for imported packages — "
        "flagged for manual review.")


# ---- Rule 6(1)(d): date -------------------------------------------------------
def check_mfg_date(text: str) -> DeclarationResult:
    t = normalize(text or "")
    if not t:
        return DeclarationResult(
            False, "Date of manufacture / packing not found.")
    d = parse_date(t)
    if d is None:
        return DeclarationResult(
            False,
            f"Date '{t[:40]}' is not in a statutory form (MM/YYYY, Month YYYY, "
            f"or DD/MM/YYYY) — Rule 6(1)(d).")
    return DeclarationResult(
        True, f"Date of manufacture {d.strftime('%m/%Y')}.")


# ---- Rule 6(1)(n): consumer care ----------------------------------------------
_PHONE_RE = re.compile(
    r"(?<![0-9])(?:"
    r"1800[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}"          # toll-free 1800
    r"|1860[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}"          # 1860 helplines
    r"|\+?91[\-\s]?[6-9][0-9]{4}[\-\s]?[0-9]{5}"        # +91 mobile
    r"|[6-9][0-9]{9}"                                   # mobile
    r"|[6-9][0-9]{4}[\-\s][0-9]{5}"                     # mobile, split
    r"|0[1-9][0-9]{1,4}[\-\s]?[0-9]{6,8}"               # landline with STD
    r"|[0-9]{3,5}[\-\s][0-9]{6,8}"                      # generic split
    r")(?![0-9])")
_EMAIL_RE = re.compile(
    r"[a-z0-9._%+\-]+\s*(?:@|\(at\))\s*[a-z0-9.\-]+\.[a-z]{2,}", re.IGNORECASE)


def check_consumer_care(text: str) -> DeclarationResult:
    t = normalize(text or "")
    if not t:
        return DeclarationResult(
            False, "Consumer care details not found (Rule 6(1)(n)).")
    phone = _PHONE_RE.search(t)
    email = _EMAIL_RE.search(t)
    pin = extract_pin(t)
    missing = []
    if phone is None:
        missing.append("telephone helpline")
    if email is None:
        missing.append("email address")
    if pin is None:
        missing.append("postal address with PIN")
    if missing:
        return DeclarationResult(
            False, f"Consumer care incomplete — missing {', '.join(missing)}.")
    return DeclarationResult(
        True,
        f"Consumer care complete (tel {phone.group(0)}, email "
        f"{email.group(0)}, PIN {pin}).", pin=pin)


# ---- Rule 6(1)(c): net quantity -------------------------------------------------
_TOLERATED_VARIANTS = {
    "nos": "N", "pcs": "piece", "pc": "piece", "units": "U",
    "pairs": "pair", "sets": "set",
}


def check_net_quantity(text: str) -> DeclarationResult:
    t = normalize(text or "")
    if not t:
        return DeclarationResult(False, "Net quantity declaration not found.")
    q = parse_quantity(t)
    if q is None:
        return DeclarationResult(
            False, f"Net quantity not decodable from '{t[:40]}'.")
    raw = q.raw_unit.lower()
    tolerated = _TOLERATED_VARIANTS.get(raw)
    if tolerated is None and not is_permitted(raw):
        return DeclarationResult(
            False,
            f"Unit '{q.raw_unit}' is not a standard SI symbol "
            f"(Rule 6(1)(c) read with Rules 11-13).")
    note = (f" (printed '{q.raw_unit}', statutory symbol '{tolerated}')"
            if tolerated is not None else "")
    return DeclarationResult(
        True, f"Net quantity {q.value} {q.unit} in standard unit{note}.")


# ---- Rule 6(1)(b): common / generic name -----------------------------------------
def check_presence(text: str, label: str) -> DeclarationResult:
    t = normalize(text or "")
    if len(t) >= 3 and any(ch.isalpha() for ch in t):
        name = label[0].upper() + label[1:]
        return DeclarationResult(
            True, f"{name} present — semantic adequacy needs manual review.")
    return DeclarationResult(False, f"{label} not found on the package.")
