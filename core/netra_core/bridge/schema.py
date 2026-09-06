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
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Any, Optional

from .. import __version__ as CORE_VERSION
from ..context import (BBox, CheckStatus, GlyphBox, OCRToken,
                       PipelineContext, Verdict)
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
    "s2_geometry_detect": "netra_core.stages.s2_geometry_detect",
    "s3_calibration": "netra_core.stages.s3_calibration",
    "s4_ocr": "netra_core.stages.s4_ocr",
    "s5_field_extract": "netra_core.stages.s5_field_extract",
    "s6_metrology": "netra_core.stages.s6_metrology",
    "s7_dossier": "netra_core.stages.s7_dossier",
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
    planned = tuple(s for s in STAGE_NAMES if s not in impl)
    try:
        import netra_core.sync            # noqa: F401
        sync_ready = True
    except Exception:
        sync_ready = False
    if not sync_ready:
        planned = planned + ("s8_sync",)
    try:
        from ..stages import s4_ocr
        engines = list(s4_ocr.registered_engines())
    except Exception:
        engines = []
    return {
        "schema_version": SCHEMA_VERSION,
        "core_version": CORE_VERSION,
        "channel": CHANNEL,
        "capabilities": {
            "stages_implemented": list(impl),
            "stages_planned": list(planned),
            "dossier": "s7_dossier" in impl,
            "signing": "platform",          # KeyStore/Secure Enclave side
            "sync": sync_ready,
            "ocr_engines": engines,
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

    raw_opts = d.get("options")
    if raw_opts is not None and not isinstance(raw_opts, dict):
        return None, _err("BAD_REQUEST", "options must be an object")
    options, opt_err = _parse_options(raw_opts)
    if opt_err is not None:
        return None, opt_err

    return ScanRequest(
        image_b64=image_b64,
        image_sha256=d.get("image_sha256"),
        shape_hint=shape_hint,
        captured_utc=captured,
        gps=gps,
        device=device,
        options=options,
    ), None


_OPT_FLOATS = ("package_height_cm", "package_width_cm", "package_diameter_cm",
               "total_surface_cm2", "marker_side_mm", "camera_focal_px")
_OPT_INTS = ("cylinder_left_px", "cylinder_right_px")


def _parse_options(raw):
    """Whitelisted, type-checked options (contract section 3). Unknown keys
    are ignored (forward compatibility); known keys with garbage values
    fail as BAD_REQUEST."""
    if raw is None:
        raw = {}
    _BOOL_KEYS = ("institutional", "fast_food", "blown", "dossier_on_pass")
    opts = {}
    for key in _BOOL_KEYS:
        v = raw.get(key)
        if v is None:
            opts[key] = False
            continue
        if not isinstance(v, bool):
            return None, _err("BAD_REQUEST",
                              f"options.{key} must be a JSON boolean "
                              f"(true/false), got {type(v).__name__}")
        opts[key] = v
    commodity = raw.get("commodity")
    if commodity is not None and not isinstance(commodity, str):
        return None, _err("BAD_REQUEST", "options.commodity must be a string")
    opts["commodity"] = commodity or ""
    for key in _OPT_FLOATS:
        v = raw.get(key)
        if v is None or v == "":
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None, _err("BAD_REQUEST", f"options.{key} must be a number")
        if not math.isfinite(f) or f <= 0:
            return None, _err("BAD_REQUEST", f"options.{key} must be positive")
        opts[key] = f
    for key in _OPT_INTS:
        v = raw.get(key)
        if v is None or v == "":
            continue
        try:
            opts[key] = int(v)
        except (TypeError, ValueError):
            return None, _err("BAD_REQUEST", f"options.{key} must be an integer")
    return opts, None


# ------------------------------------------------------- scan_tokens (v1.3)
_TOKEN_ENGINES = ("mlkit", "tesseract", "indic", "bhashini")


@dataclass(frozen=True)
class ScanTokensRequest:
    """Contract v1.3 scan_tokens request — the B1 device path input."""
    tokens: tuple
    quality: Optional[dict] = None
    geometry: Optional[dict] = None
    glyphs: tuple = ()
    image_b64: Optional[str] = None
    image_sha256: Optional[str] = None
    shape_hint: str = ""
    captured_utc: Optional[datetime] = None
    gps: Optional[dict] = None
    device: Optional[dict] = None
    options: dict = field(default_factory=dict)


def _bbox_ok(v) -> bool:
    return (isinstance(v, list) and len(v) == 4
            and all(isinstance(n, int) and not isinstance(n, bool) for n in v)
            and v[0] >= 0 and v[1] >= 0 and v[2] > 0 and v[3] > 0)


def scan_tokens_request_from_dict(d: Any) -> tuple:
    """-> (ScanTokensRequest, None) or (None, error-dict). Mirrors the
    validation discipline of scan_request_from_dict; quality / geometry /
    glyphs / image are all OPTIONAL — the request degrades exactly as
    far as it is incomplete (Dart-only builds send tokens + options)."""
    if not isinstance(d, dict):
        return None, _err("BAD_REQUEST", "request body must be a JSON object")
    version = d.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        return None, _err("UNSUPPORTED_VERSION",
                          f"bridge schema {SCHEMA_VERSION} expected, got {version!r}")

    raw_tokens = d.get("tokens")
    if not isinstance(raw_tokens, list) or not raw_tokens:
        return None, _err("BAD_REQUEST",
                          "'tokens' (non-empty list of OCR line tokens) is required")
    tokens = []
    for i, t in enumerate(raw_tokens):
        if not isinstance(t, dict):
            return None, _err("BAD_REQUEST", f"tokens[{i}] must be an object")
        text = t.get("text")
        if not isinstance(text, str) or not text:
            return None, _err("BAD_REQUEST",
                              f"tokens[{i}].text must be a non-empty string")
        if not _bbox_ok(t.get("bbox")):
            return None, _err("BAD_REQUEST",
                              f"tokens[{i}].bbox must be [x, y, w, h] ints (w, h > 0)")
        conf = t.get("conf", 1.0)
        if (not isinstance(conf, (int, float)) or isinstance(conf, bool)
                or not 0.0 <= float(conf) <= 1.0):
            return None, _err("BAD_REQUEST", f"tokens[{i}].conf must be 0..1")
        engine = t.get("engine", "mlkit")
        if engine not in _TOKEN_ENGINES:
            return None, _err("BAD_REQUEST",
                              f"tokens[{i}].engine must be one of {_TOKEN_ENGINES}")
        lang = t.get("lang", "en")
        if not isinstance(lang, str):
            return None, _err("BAD_REQUEST", f"tokens[{i}].lang must be a string")
        tokens.append(OCRToken(text=text, bbox=BBox.from_list(t["bbox"]),
                                conf=round(float(conf), 3),
                                engine=engine, lang=lang))

    q = d.get("quality")
    if q is not None:
        if not isinstance(q, dict):
            return None, _err("BAD_REQUEST", "quality must be an object")
        if q.get("ok") is not None and not isinstance(q.get("ok"), bool):
            return None, _err("BAD_REQUEST", "quality.ok must be bool or null")
        prompts = q.get("prompts", [])
        if (not isinstance(prompts, list)
                or not all(isinstance(p, str) for p in prompts)):
            return None, _err("BAD_REQUEST",
                              "quality.prompts must be a list of strings")
        for k in ("laplacian_var", "glare_pct"):
            v = q.get(k)
            if v is not None and (not isinstance(v, (int, float))
                                  or isinstance(v, bool)):
                return None, _err("BAD_REQUEST",
                                  f"quality.{k} must be number or null")
        if q.get("glare_bbox") is not None and not _bbox_ok(q.get("glare_bbox")):
            return None, _err("BAD_REQUEST",
                              "quality.glare_bbox must be bbox or null")

    g = d.get("geometry")
    if g is not None:
        if not isinstance(g, dict):
            return None, _err("BAD_REQUEST", "geometry must be an object")
        for k in ("shape", "shape_detected"):
            v = g.get(k)
            if v is not None and v not in SHAPE_HINTS:
                return None, _err("BAD_REQUEST",
                                  f"geometry.{k} must be a shape or null")
        for k in ("mm_per_px", "pda_cm2"):
            v = g.get(k)
            if v is not None and (not isinstance(v, (int, float))
                                  or isinstance(v, bool) or v <= 0):
                return None, _err("BAD_REQUEST",
                                  f"geometry.{k} must be a positive number or null")
        if g.get("pda_method") is not None and \
                not isinstance(g.get("pda_method"), str):
            return None, _err("BAD_REQUEST",
                              "geometry.pda_method must be a string or null")
        rois = g.get("rois", [])
        if not isinstance(rois, list):
            return None, _err("BAD_REQUEST", "geometry.rois must be a list")
        for i, r in enumerate(rois):
            if (not isinstance(r, dict) or not isinstance(r.get("roi"), str)
                    or not _bbox_ok(r.get("bbox"))):
                return None, _err("BAD_REQUEST",
                                  f"geometry.rois[{i}] must be {{roi, bbox, conf?}}")
            c = r.get("conf", 0.0)
            if (not isinstance(c, (int, float)) or isinstance(c, bool)
                    or not 0.0 <= float(c) <= 1.0):
                return None, _err("BAD_REQUEST",
                                  f"geometry.rois[{i}].conf must be 0..1")

    raw_glyphs = d.get("glyphs")
    glyphs = []
    if raw_glyphs is not None:
        if not isinstance(raw_glyphs, list):
            return None, _err("BAD_REQUEST", "glyphs must be a list")
        for i, gl in enumerate(raw_glyphs):
            if not isinstance(gl, dict):
                return None, _err("BAD_REQUEST", f"glyphs[{i}] must be an object")
            name = gl.get("glyph")
            h, w = gl.get("height_mm"), gl.get("width_mm")
            if (not isinstance(name, str) or not name
                    or not isinstance(h, (int, float)) or isinstance(h, bool) or h <= 0
                    or not isinstance(w, (int, float)) or isinstance(w, bool) or w < 0):
                return None, _err("BAD_REQUEST",
                                  f"glyphs[{i}] needs glyph, height_mm > 0, width_mm >= 0")
            glyphs.append(GlyphBox(glyph=name, height_mm=float(h),
                                   width_mm=float(w)))

    image_b64 = d.get("image_b64")
    if image_b64 is not None and not isinstance(image_b64, str):
        return None, _err("BAD_REQUEST", "image_b64 must be a string")
    image_sha = d.get("image_sha256")
    if image_sha is not None and not isinstance(image_sha, str):
        return None, _err("BAD_REQUEST", "image_sha256 must be a string")

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
    if gps is not None and (not isinstance(gps, dict)
                            or not isinstance(gps.get("lat"), (int, float))
                            or not isinstance(gps.get("lon"), (int, float))):
        return None, _err("BAD_REQUEST", "gps requires numeric 'lat' and 'lon'")
    device = d.get("device")
    if device is not None and not isinstance(device, dict):
        return None, _err("BAD_REQUEST", "device must be an object")
    raw_opts = d.get("options")
    if raw_opts is not None and not isinstance(raw_opts, dict):
        return None, _err("BAD_REQUEST", "options must be an object")
    options, opt_err = _parse_options(raw_opts)
    if opt_err is not None:
        return None, opt_err

    return ScanTokensRequest(
        tokens=tuple(tokens), quality=q, geometry=g, glyphs=tuple(glyphs),
        image_b64=image_b64, image_sha256=image_sha, shape_hint=shape_hint,
        captured_utc=captured, gps=gps, device=device, options=options), None


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


def _meta_out(request: Optional[ScanRequest | ScanTokensRequest], ctx: Optional[PipelineContext] = None) -> Optional[dict]:
    if request is not None:
        return {"gps": request.gps, "device": request.device,
                "options": request.options}
    if ctx is not None and ctx.meta:
        m = dict(ctx.meta)
        return {"gps": m.get("gps"), "device": m.get("device"),
                "options": m.get("options")}
    return None


def _empty_quality() -> dict:
    return {"ok": None, "laplacian_var": None, "glare_pct": None,
            "prompts": [], "glare_bbox": None}


def result_from_context(ctx: PipelineContext, *, request: Optional[ScanRequest | ScanTokensRequest] = None,
                        error: Optional[dict] = None) -> dict:
    """Serialize a finished PipelineContext into contract v1 JSON."""
    s1_ok = {s.stage: s.ok for s in ctx.stages}.get("s1_frame_quality")
    q = ctx.quality or {}
    quality = {
        "ok": s1_ok if s1_ok is not None else q.get("ok"),
        "laplacian_var": q.get("laplacian_var"),
        "glare_pct": q.get("glare_pct"),
        "prompts": list(q.get("prompts", [])),
        "glare_bbox": q.get("glare_bbox"),
    }

    if (ctx.mm_per_px is None and ctx.pda_cm2 is None and not ctx.shape_hint
            and not ctx.shape_detected and not ctx.rois):
        geometry = None
    else:
        geometry = {
            "shape": ctx.shape_hint or ctx.shape_detected or None,
            "shape_detected": ctx.shape_detected or None,
            "mm_per_px": ctx.mm_per_px,
            "pda_cm2": ctx.pda_cm2,
            "pda_method": ctx.pda_method or None,
            "rois": [{"roi": r["roi"], "bbox": r["bbox"].to_list(),
                      "conf": r["conf"]} for r in ctx.rois],
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

    from ..rules.plain_messages import plain_for
    checks = [{"rule": c.rule, "status": c.status.value, "message": c.message,
               "plain": plain_for(c.rule, c.status.value, c.message),
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
        "meta": _meta_out(request, ctx),
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
