"""Plain-language inspector phrasing for statutory findings.

Two voices, one source: `message` in checks is the statutory/court voice
(dossier, citations); `plain` is the field voice — what an inspector
reads on a phone in daylight. Generated in the core (never Dart) so the
law and its translation can't drift apart.
"""
from __future__ import annotations

# (rule, status) -> template over {field}. Missing pair -> None (Dart
# falls back to the statutory message).
_PLAIN = {
    ("13", "FAIL"): "The label says '{token}' — the correct unit symbol is '{fix}'.",
    ("13", "PASS"): "Unit spellings are correct.",
    ("6(1)(c)", "FAIL"): "The net quantity is printed in a non-standard unit.",
    ("6(1)(c)", "PASS"): "Net quantity is declared correctly.",
    ("6(1)(e)", "FAIL"): "The MRP declaration is non-compliant or missing required statutory wording.",
    ("6(1)(e)", "PASS"): "MRP is declared with the required tax wording.",
    ("6(11)", "FAIL"): "The unit price printed on the pack doesn't match the MRP.",
    ("6(11)", "PASS"): "The unit price matches the MRP.",
    ("6(11)", "NA"): "Unit price couldn't be checked — MRP or quantity missing.",
    ("6(1)(d)", "FAIL"): "The manufacturing date is missing or not in a valid Month-Year format.",
    ("6(1)(d)", "PASS"): "Manufacturing date is valid.",
    ("6(1)(a)", "FAIL"): "Maker's name and full postal address (with PIN code) is incomplete.",
    ("6(1)(a)", "PASS"): "Maker's details with PIN code are complete.",
    ("6(1)(aa)", "FAIL"): "Country of origin is missing or unclear.",
    ("6(1)(aa)", "PASS"): "Country of origin is clearly stated.",
    ("6(1)(aa)", "NA"): "Country of origin not found — required only for imported items.",
    ("6(1)(n)", "FAIL"): "Consumer care details are incomplete (helpline / email / address).",
    ("6(1)(n)", "PASS"): "Consumer care details are complete.",
    ("6(1)(b)", "FAIL"): "The product's common/generic name is missing.",
    ("6(1)(b)", "PASS"): "Product name is present.",
    ("7", "FAIL"): "The printed letters are smaller than the legal minimum for this pack size.",
    ("7", "PASS"): "Letter heights meet the legal minimum.",
    ("7", "NA"): "Letter height couldn't be measured — hold the calibration card in frame (or confirm pack dimensions).",
    ("7(3)", "FAIL"): "Some letters are too narrow (width must be at least 1/3 of height).",
    ("7(3)", "PASS"): "Letter widths are compliant.",
    ("26", "NA"): "This pack is exempt from declaration rules ({note}).",
}

_TOKEN_FIX = {"gms": "g", "grm": "g", "kilo": "kg", "kgs": "kg",
              "ltr": "L", "cc": "mL", "pkts": "piece", "doz": "piece"}


def plain_for(rule: str, status: str, message: str = "") -> str:
    """Field-voice rendering of a check; statutory message as fallback."""
    low = message.lower()

    # Specialized phrasing for Rule 6(1)(e) (MRP) based on specific failure cause
    if rule == "6(1)(e)" and status == "FAIL":
        if "not detected" in low or "not found" in low:
            return "The Maximum Retail Price (MRP) declaration was not found on the package."
        if "inclusive of all taxes" in low or "tax" in low:
            return "The MRP is printed, but mandatory phrase 'inclusive of all taxes' is missing."
        if "rupee amount" in low:
            return "The MRP is printed without a valid retail price amount."
        if "wording" in low or "keyword" in low:
            return "The price is printed, but 'MRP' / 'Maximum Retail Price' wording is missing."
        if "missing" in low:
            missing_detail = message.split("missing", 1)[-1].strip().rstrip(".")
            return f"The MRP declaration is incomplete: missing {missing_detail}."
        return "The MRP declaration is non-compliant or missing required statutory wording."

    tmpl = _PLAIN.get((rule, status))
    if tmpl is None:
        return message
    kwargs = {}
    for bad, good in _TOKEN_FIX.items():
        if f"'{bad}'" in low:
            kwargs = {"token": bad, "fix": good}
            break
    if "{note}" in tmpl:
        kwargs["note"] = message.split(". ", 1)[-1].rstrip(".") or \
            "small/bulk/institutional exemption"
    try:
        formatted = tmpl.format(**kwargs)
        if "{" in formatted and "}" in formatted:
            if rule == "13" and status == "FAIL":
                return "The printed unit symbol is non-standard or misspelled."
            return message or "Declaration non-compliant with statutory rules."
        return formatted
    except (KeyError, IndexError, ValueError):
        if rule == "13" and status == "FAIL":
            return "The printed unit symbol is non-standard or misspelled."
        if rule == "26" and status == "NA":
            return "This pack is exempt from declaration rules."
        return message or "Declaration non-compliant with statutory rules."
