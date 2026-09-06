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
    ("6(1)(e)", "FAIL"): "The MRP is printed but '{missing}' — this wording is legally required.",
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
    tmpl = _PLAIN.get((rule, status))
    if tmpl is None:
        return message
    kwargs = {}
    low = message.lower()
    for bad, good in _TOKEN_FIX.items():
        if f"'{bad}'" in low:
            kwargs = {"token": bad, "fix": good}
            break
    if "inclusive of all taxes" in low and status == "FAIL":
        kwargs["missing"] = "'incl. of all taxes' is missing"
    if "{note}" in tmpl:
        kwargs["note"] = message.split(". ", 1)[-1].rstrip(".") or \
            "small/bulk/institutional exemption"
    try:
        return tmpl.format(**kwargs)
    except KeyError:
        return tmpl
