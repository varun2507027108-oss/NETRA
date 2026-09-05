"""Fixture ground-truth comparison — the golden-report engine (stdlib).

scripts/make_fixtures.py drives the full pipeline per fixture photograph
and feeds each contract ScanResult here; this module diffs it against
fixtures/labels_gt.json and aggregates. Pure and deterministic — unit
tested with synthetic results, no OCR required.

Comparison policy (OCR-tolerant, content-exact):
- rules: set equality of FAILED rule keys vs entry.expect_fail
- fields: normalized containment expected-in-extracted (case, whitespace,
  punctuation and the rupee glyph <-> 'rs' are treated equal; a SHORTER
  extraction than ground truth never passes)
- verdict: VIOLATION iff expect_fail non-empty (else PASS); a clean RETRY
  is a CAPTURE problem (blur / fiducial / no text) — reported separately,
  never scored as a logic failure; in-band errors are classification
  'error', not capture

Ground-truth schema (per fixture key):
    shape        rectangular|cylindrical|pouch|bottle|blister|other
    dims_cm      {height, width} | {height, diameter} | {total_surface}
    fields       {field_key: exactly what is printed}
    expect_fail  [rule keys]  ([] = expected compliant)
    options?     passthrough (institutional, fast_food, commodity...)
    notes?       free text
"""
from __future__ import annotations

import re
from typing import Optional

_SHAPE_HINTS = ("rectangular", "cylindrical", "pouch", "bottle",
                "blister", "other")


def normalize_for_compare(text: str) -> str:
    t = (text or "").lower()
    t = t.replace("₹", " rs ")
    t = re.sub(r"\brs\.?\b", "rs", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def field_match(expected: str, extracted: Optional[str]) -> bool:
    if extracted is None:
        return False
    e = normalize_for_compare(expected)
    x = normalize_for_compare(extracted)
    return bool(e) and (e == x or e in x)


def build_options(entry: dict) -> dict:
    """Ground-truth entry -> contract options (dims -> PDA inputs)."""
    opts = dict(entry.get("options") or {})
    dims = entry.get("dims_cm") or {}
    if dims.get("height"):
        opts.setdefault("package_height_cm", float(dims["height"]))
    if dims.get("width"):
        opts.setdefault("package_width_cm", float(dims["width"]))
    if dims.get("diameter"):
        opts.setdefault("package_diameter_cm", float(dims["diameter"]))
    if dims.get("total_surface"):
        opts.setdefault("total_surface_cm2", float(dims["total_surface"]))
    return opts


def validate_entry(key: str, entry) -> list:
    if not isinstance(entry, dict):
        return [f"{key}: entry must be an object"]
    problems = []
    shape = entry.get("shape", "")
    if shape not in _SHAPE_HINTS:
        problems.append(f"{key}: shape must be one of {_SHAPE_HINTS}")
    dims = entry.get("dims_cm") or {}
    if not isinstance(dims, dict):
        problems.append(f"{key}: dims_cm must be an object")
    elif shape in ("rectangular", "pouch") and not (
            dims.get("height") and dims.get("width")):
        problems.append(f"{key}: flat shapes want height+width for PDA")
    fields = entry.get("fields")
    if not isinstance(fields, dict) or not fields:
        problems.append(f"{key}: fields (what is printed) required")
    expect = entry.get("expect_fail")
    if expect is not None and not isinstance(expect, list):
        problems.append(f"{key}: expect_fail must be a list of rule keys")
    return problems


def compare_fixture(entry: dict, result: dict) -> dict:
    """Diff one contract ScanResult against its ground-truth entry."""
    expected_rules = set(entry.get("expect_fail") or [])
    failed = {c.get("rule") for c in result.get("checks") or []
              if c.get("status") == "FAIL"}
    verdict = result.get("verdict")
    err = result.get("error")

    fields_ok, fields_missing, fields_mismatch = [], [], {}
    for key, expected_raw in (entry.get("fields") or {}).items():
        got = (result.get("fields") or {}).get(key)
        if got is None:
            fields_missing.append(key)
        elif field_match(str(expected_raw), got.get("raw")):
            fields_ok.append(key)
        else:
            fields_mismatch[key] = {"expected": str(expected_raw),
                                    "got": got.get("raw")}

    if err is not None:
        status = "error"
    elif verdict == "RETRY":
        status = "capture_retry"
    elif (failed == expected_rules and not fields_missing
            and not fields_mismatch):
        status = "ok"
    else:
        status = "mismatch"

    return {
        "status": status,
        "verdict": verdict,
        "expected_verdict": "VIOLATION" if expected_rules else "PASS",
        "failed_rules": sorted(failed),
        "expected_rules": sorted(expected_rules),
        "missing_fail": sorted(expected_rules - failed),
        "extra_fail": sorted(failed - expected_rules),
        "fields_ok": sorted(fields_ok),
        "fields_missing": sorted(fields_missing),
        "fields_mismatch": fields_mismatch,
        "retry_prompts": (result.get("quality") or {}).get("prompts") or [],
        "tokens_decoded": len((result.get("ocr") or {}).get("tokens") or []),
        "error": err,
    }


def summarize(outcomes: dict) -> dict:
    """Aggregate per-fixture outcomes: counts, rule precision/recall,
    field extraction rate. capture_retry and error rows are excluded
    from the scores (they are capture/infra problems, not logic)."""
    values = list(outcomes.values())
    mismatched = [k for k, v in outcomes.items() if v["status"] == "mismatch"]
    retries = [k for k, v in outcomes.items() if v["status"] == "capture_retry"]
    errors = [k for k, v in outcomes.items() if v["status"] == "error"]

    tp = fp = fn = 0
    for v in values:
        if v["status"] in ("capture_retry", "error"):
            continue
        expected, failed = set(v["expected_rules"]), set(v["failed_rules"])
        tp += len(expected & failed)
        fn += len(v["missing_fail"])
        fp += len(v["extra_fail"])

    fields_expected = fields_found = 0
    for v in values:
        n = (len(v["fields_ok"]) + len(v["fields_missing"])
             + len(v["fields_mismatch"]))
        fields_expected += n
        fields_found += len(v["fields_ok"])

    return {
        "fixtures": len(values),
        "ok": sum(1 for v in values if v["status"] == "ok"),
        "mismatch": len(mismatched),
        "mismatched": mismatched,
        "capture_retry": retries,
        "errors": errors,
        "rule_tp": tp, "rule_fp": fp, "rule_fn": fn,
        "rule_precision": tp / (tp + fp) if tp + fp else None,
        "rule_recall": tp / (tp + fn) if tp + fn else None,
        "field_extraction_rate":
            fields_found / fields_expected if fields_expected else None,
    }
