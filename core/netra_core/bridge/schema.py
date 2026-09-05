"""NETRA bridge contract v1 — schema, validation, serialization.

The machine-readable twin of docs/BRIDGE_CONTRACT.md (the human-readable
source of truth). Deliberately stdlib-only:

- identical behaviour in pytest, in the desktop FastAPI bridge, and inside
  Chaquopy on Android (no pydantic — its v2 Rust core is a bad wheel to
  fight on ARM);
- all 17 result keys are ALWAYS present; optional = null (Dart null-safety);
- money/quantities serialize as strings so no JSON parser ever turns
  "14.00" into a float;
- bbox = [x, y, w, h] ints in the pixel space of the submitted image;
- timestamps are ISO-8601 UTC, millisecond precision, trailing Z.

RESULT_KEYS is frozen: adding a key without bumping SCHEMA_VERSION and this
tuple fails tests/test_bridge_schema.py on purpose.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Any, Optional

from .. import __version__ as CORE_VERSION
from ..context import CheckStatus, PipelineContext, Verdict
from ..rules.citations import citation

SCHEMA_VERSION = 1
CHANNEL = "netra.core"

# canonical stage identifiers (s8_sync is async — never in timings_ms)
STAGE_NAMES = (
    "s1_frame_quality", "s2_geometry_detect", "s3_calibration", "s4_ocr",
    "s5_field_extract", "s6_metrology", "s7_dossier",
)

# modules that exist today; grows one line per stage as s2-s5, s7 land
_STAGE_MODULES = {
    "s1_frame_quality": "netra_core.stages.s1_frame_quality",
    "s6_metrology": "netra_core.stages.s6_metrology",
}

SHAPE_HINTS = ("rectangular", "cylindrical", "pouch", "bottle", "blister", "other")

ERROR_CODES = ("BAD_REQUEST", "DECODE_ERROR", "UNSUPPORTED_VERSION",
               "STAGE_FAILURE", "INTERNAL")

RESULT_KEYS = (
    "schema_version", "scan_id", "verdict", "captured_utc", "completed_utc",
    "total_ms", "timings_ms", "quality", "geometry", "ocr", "fields",
    "checks", "exemption", "summary", "dossier", "meta", "error",
)


# --------------------------------------------------------------- capabilities
@lru_cache(maxsize=1)
def implemented_stages() -> tuple:
    """Stage names whose modules import cleanly in this environment."""
    out = []
    for name in STAGE_NAMES:
        modname = _STAGE_MODULES.get(name)
        if modname is None:
            continue
        try:
            importlib.import_module(modname)
        except Exception:          # cv2 missing, etc. — capability, not a crash
            continue
        out.append(name)
    return tuple(out)


def ping_payload() -> dict:
    impl = implemented_stages()
    planned = tuple(s for s in STAGE_NAMES if s not in impl) + ("s8_sync",)
    return {
        "schema_version": SCHEMA_VERSION,
        "core_version": CORE_VERSION,
        "channel": CHANNEL,
        "capabilities": {
            "stages_implemented": list(impl),
            "stages_planned": list(planned),
            "dossier": "s7_dossier" in impl,
            "signing": "platform",          # KeyStore/Secure Enclave side
        },
    }


# -------------------------------------------------------------------- request
@dataclass(frozen=True)
class ScanRequest:
    image_b64: str
    image_sha256: Optional[str] = None
    shape_hint: str = ""
    captured_utc: Optional[datetime] = None
    gps: Optional[dict] = None          # {lat, lon, accuracy_m?}
    device: Optional[dict] = None       # {model, os, app_build?}
    options: dict = field(default_factory=dict)   # s6: institutional etc.


def _err(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def scan_request_from_dict(d: Any) -> tuple:
    """-> (ScanRequest, None) or (None, error-dict). Unknown keys ignored
    (forward compatibility, per contract section 7)."""
    if not isinstance(d, dict):
        return None, _err("BAD_REQUEST", "request body must be a JSON object")

    version = d.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        return None, _err("UNSUPPORTED_VERSION",
                          f"bridge schema {SCHEMA_VERSION} expected, got {version!r}")

    image_b64 = d.get("image_b64")
    if not isinstance(image_b64, str) or not image_b64:
        return None, _err("BAD_REQUEST", "'image_b64' (base64 JPEG/PNG) is required")

    shape_hint = d.get("shape_hint") or ""
    if shape_hint and shape_hint not in SHAPE_HINTS:
        return None, _err("BAD_REQUEST", f"shape_hint must be one of {SHAPE_HINTS}")

    captured = d.get("captured_utc")
    if captured:
        try:
            captured = datetime.fromisoformat(str(captured).replace("Z", "+00:00"))
        except ValueError:
            return None, _err("BAD_REQUEST", "captured_utc must be ISO-8601")

    gps = d.get("gps")
    if gps is not None and (
            not isinstance(gps, dict)
            or not isinstance(gps.get("lat"), (int, float))
            or not isinstance(gps.get("lon"), (int, float))):
        return None, _err("BAD_REQUEST", "gps requires numeric 'lat' and 'lon'")

    device = d.get("device")
    if device is not None and not isinstance(device, dict):
        return None, _err("BAD_REQUEST", "device must be an object")

    raw_opts = d.get("options") or {}
    if not isinstance(raw_opts, dict):
        return None, _err("BAD_REQUEST", "options must be an object")
    options = {
        "institutional": bool(raw_opts.get("institutional", False)),
        "fast_food": bool(raw_opts.get("fast_food", False)),
        "commodity": str(raw_opts.get("commodity") or ""),
    }

    return ScanRequest(
        image_b64=image_b64,
        image_sha256=d.get("image_sha256"),
        shape_hint=shape_hint,
        captured_utc=captured,
        gps=gps,
        device=device,
        options=options,
    ), None


# --------------------------------------------------------------- serialization
def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds") \
             .replace("+00:00", "Z")


def _value_out(v: Any) -> Optional[str]:
    """Statutory values cross the bridge as strings — never floats."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime):
        return _iso_z(v)
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _bbox_out(b) -> Optional[list]:
    return b.to_list() if b is not None else None


def _meta_out(request: Optional[ScanRequest]) -> Optional[dict]:
    if request is None:
        return None
    return {"gps": request.gps, "device": request.device,
            "options": request.options}


def _empty_quality() -> dict:
    return {"ok": None, "laplacian_var": None, "glare_pct": None,
            "prompts": [], "glare_bbox": None}


def result_from_context(ctx: PipelineContext, *, request: Optional[ScanRequest] = None,
                        error: Optional[dict] = None) -> dict:
    """Serialize a finished PipelineContext into contract v1 JSON."""
    s1_ok = {s.stage: s.ok for s in ctx.stages}.get("s1_frame_quality")
    q = ctx.quality or {}
    quality = {
        "ok": s1_ok,
        "laplacian_var": q.get("laplacian_var"),
        "glare_pct": q.get("glare_pct"),
        "prompts": list(q.get("prompts", [])),
        "glare_bbox": q.get("glare_bbox"),
    }

    if ctx.mm_per_px is None and ctx.pda_cm2 is None and not ctx.shape_hint:
        geometry = None
    else:
        geometry = {
            "shape": ctx.shape_hint or None,
            "mm_per_px": ctx.mm_per_px,
            "pda_cm2": ctx.pda_cm2,
            "pda_method": ctx.pda_method or None,
            "rois": [],                      # filled by s2 when it lands
        }

    tokens = [{"text": t.text, "bbox": _bbox_out(t.bbox),
               "conf": round(float(t.conf), 3),
               "engine": t.engine, "lang": t.lang} for t in ctx.tokens]
    ocr = {"engines_used": sorted({t.engine for t in ctx.tokens}),
           "tokens": tokens}

    fields = {k: {"raw": fv.raw, "value": _value_out(fv.value),
                  "unit": fv.unit, "bbox": _bbox_out(fv.bbox),
                  "conf": round(float(fv.conf), 3)}
              for k, fv in ctx.fields.items()}

    checks = [{"rule": c.rule, "status": c.status.value, "message": c.message,
               "citation": citation(c.rule), "evidence_bbox": _bbox_out(c.evidence)}
              for c in ctx.checks]

    if ctx.exemption is not None:
        exemption = {"exempt": ctx.exemption.exempt,
                     "clause": ctx.exemption.clause, "note": ctx.exemption.note}
    else:
        exemption = None

    counts = {"PASS": 0, "FAIL": 0, "NA": 0}
    for c in checks:
        counts[c["status"]] += 1
    summary = {"total": len(checks), "pass": counts["PASS"],
               "fail": counts["FAIL"], "na": counts["NA"]}

    if ctx.dossier_sha256:
        dossier = {"sha256": ctx.dossier_sha256,
                   "pdf_path": ctx.dossier_path or None,
                   "signed": False, "signature": None, "cert_pem": None,
                   "sig_status": "pending"}
    else:
        dossier = None

    return {
        "schema_version": SCHEMA_VERSION,
        "scan_id": ctx.image_id,
        "verdict": "RETRY" if error else ctx.verdict.value,
        "captured_utc": _iso_z(ctx.captured_utc),
        "completed_utc": _iso_z(datetime.now(timezone.utc)),
        "total_ms": round(ctx.total_ms, 2),
        "timings_ms": {s.stage: round(s.duration_ms, 2) for s in ctx.stages},
        "quality": quality,
        "geometry": geometry,
        "ocr": ocr,
        "fields": fields,
        "checks": checks,
        "exemption": exemption,
        "summary": summary,
        "dossier": dossier,
        "meta": _meta_out(request),
        "error": error,
    }


def error_result(code: str, message: str, *, stage: Optional[str] = None,
                 scan_id: Optional[str] = None,
                 request: Optional[ScanRequest] = None) -> dict:
    """Contract-shaped failure — never raise across the bridge."""
    now = datetime.now(timezone.utc)
    captured = request.captured_utc if request and request.captured_utc else now
    return {
        "schema_version": SCHEMA_VERSION,
        "scan_id": scan_id or "",
        "verdict": "RETRY",
        "captured_utc": _iso_z(captured),
        "completed_utc": _iso_z(now),
        "total_ms": 0.0,
        "timings_ms": {},
        "quality": _empty_quality(),
        "geometry": None,
        "ocr": {"engines_used": [], "tokens": []},
        "fields": {},
        "checks": [],
        "exemption": None,
        "summary": {"total": 0, "pass": 0, "fail": 0, "na": 0},
        "dossier": None,
        "meta": _meta_out(request),
        "error": {"code": code, "message": message, "stage": stage},
    }
