"""Institutional export payload builders — e-Daakhil & NCH 1915.

These builders produce STANDARDIZED JSON from a ledger row or a sync
envelope (client.envelope_from_row output — both shapes accepted). The
actual e-Daakhil and NCH 1915 submission APIs require institutional
credentials and integration approval (Department of Consumer Affairs);
NETRA's contract is to emit the payloads with the evidence chain intact.
The institutional gateway exposes them per scan; when credentials exist,
a delivery adapter posts these payloads verbatim.

Pure stdlib. Respondent extraction strips declaration labels ("Mfd. by:",
"Imported by:", ...) from the OCR address; PIN-zone routing maps the first
digit of the manufacturer/consumer-care PIN to India's postal zones.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

from ..rules.declarations import extract_pin

PIN_ZONES = {
    "1": "Delhi / Haryana / Punjab / Himachal Pradesh / J&K / Chandigarh",
    "2": "Uttar Pradesh / Uttarakhand",
    "3": "Rajasthan / Gujarat / Daman & Diu",
    "4": "Maharashtra / Madhya Pradesh / Goa / Chhattisgarh",
    "5": "Telangana / Andhra Pradesh / Karnataka",
    "6": "Tamil Nadu / Kerala / Puducherry / Lakshadweep",
    "7": "West Bengal / Odisha / Assam / North-East / Andaman",
    "8": "Bihar / Jharkhand",
    "9": "Army Postal Service",
}

_LABEL_RE = re.compile(
    r"^\s*(?:mfd\.?|mfg\.?|mktd\.?|manufactur(?:ed|er|ers|ing)?|"
    r"import(?:er|ed|ers)?|pack(?:er|ed|ing)?|market(?:er|ed|ing)?)"
    r"[^:]{0,24}:\s*", re.IGNORECASE)


def _result(row: dict) -> dict:
    result = row.get("result")
    if result is None and row.get("result_json"):
        try:
            result = json.loads(row["result_json"])
        except (json.JSONDecodeError, TypeError):
            result = {}
    return result if isinstance(result, dict) else {}


def _raw(row: dict, key: str) -> str:
    return ((_result(row).get("fields") or {}).get(key) or {}).get("raw") or ""


def _failed_checks(row: dict) -> list:
    return [c for c in _result(row).get("checks") or []
            if c.get("status") == "FAIL"]


def _respondent(row: dict) -> dict:
    raw = _raw(row, "mfg_address")
    name = _LABEL_RE.sub("", raw).split(",")[0].strip()
    return {
        "name": name or "Not declared on package (Rule 6(1)(a) finding)",
        "address_as_declared": raw or "Not declared on package",
    }


def _pin_zone(row: dict) -> Optional[str]:
    for key in ("mfg_address", "consumer_care"):
        pin = extract_pin(_raw(row, key))
        if pin:
            return PIN_ZONES.get(pin[0], f"PIN zone {pin[0]}")
    return None


def _evidence(row: dict) -> dict:
    return {
        "netra_scan_id": row.get("scan_id"),
        "image_sha256": row.get("image_sha256"),
        "dossier_sha256": row.get("dossier_sha256"),
        "dossier_signature": row.get("signature"),
        "signature_algorithm": "ECDSA P-256 with SHA-256 "
                               "(hardware-backed on the capture device)",
        "signature_status": row.get("sig_status") or "pending",
        "signature_verified_by_core": bool(row.get("sig_verified")),
        "certificate_pem": row.get("cert_pem"),
    }


def _generated() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds") \
        .replace("+00:00", "Z")


def edakakhil_payload(row: dict) -> dict:
    """Consumer-case filing payload (e-Daakhil shape, NETRA envelope)."""
    failures = _failed_checks(row)
    return {
        "export": "edakakhil",
        "generated_utc": _generated(),
        "case": {
            "complaint_category": "Legal Metrology — Packaged Commodities",
            "statute": {
                "act": "Legal Metrology Act, 2009",
                "rules": "Legal Metrology (Packaged Commodities) Rules, 2011",
            },
            "complainant": {
                "role": "Legal Metrology Inspector (NETRA field audit)",
                "name": "", "designation": "", "office_address": "",
                "note": "to be completed by the filing officer",
            },
            "respondent": _respondent(row),
            "violations": [
                {"rule": c.get("rule"), "citation": c.get("citation"),
                 "finding": c.get("message")} for c in failures],
            "relief_sought": "Action under the Legal Metrology Act, 2009 and "
                             "the LMPC Rules, 2011; corrective re-labelling "
                             "of the impugned stock.",
            "evidence": _evidence(row),
        },
    }


def nch1915_payload(row: dict) -> dict:
    """National Consumer Helpline (1915) complaint payload."""
    failures = _failed_checks(row)
    summary = "; ".join(
        f"[Rule {c.get('rule')}] {(c.get('message') or '')[:160]}"
        for c in failures)
    return {
        "export": "nch1915",
        "generated_utc": _generated(),
        "complaint": {
            "category": "Misleading labelling / packaged commodity "
                        "declaration defect",
            "brand_or_product": _raw(row, "product_name") or "not decoded",
            "manufacturer_address": _raw(row, "mfg_address")
                                    or "not declared",
            "pin_zone": _pin_zone(row),
            "description": (
                f"Automated NETRA field audit found {len(failures)} "
                f"statutory non-compliance(s): {summary}" if failures else
                "Automated NETRA field audit found the package compliant."),
            "evidence": _evidence(row),
        },
    }
