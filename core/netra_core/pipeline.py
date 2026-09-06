"""NETRA pipeline orchestrator — two scan paths, one contract.

run_scan        (image path, full-stack / desktop): stages in statutory
                order. Vision stages (s1/s2/s3) load LAZILY — on a B1
                device build (no cv2) the method returns an in-band
                STAGE_FAILURE envelope pointing at scan_tokens instead
                of crashing the channel.

run_scan_tokens (B1 device path, contract v1.3): the platform supplies
                OCR line tokens (ML Kit) plus optional quality, geometry,
                metric scale and glyph measurements; Python runs
                s4(injection) -> s5 -> s6 -> s7 over them and returns the
                identical 17-key ScanResult with the same ledger, dossier
                and signing semantics. No vision dependency is required
                anywhere in this path.

attach_signature: contract section 8 handshake.

run_demo_scan: desktop demo (dev injection + synthetic frame); cv2 is
                required at CALL time, never at import time.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import importlib
import io
import sys
from dataclasses import replace

from .bridge.schema import (SCHEMA_VERSION, ScanRequest, error_result,
                            result_from_context)
from .config import PDA_SANITY_CM2
from .context import BBox, OCRToken, PipelineContext
from .dossier import crypto
from .persistence import queue_db
from .stages import s4_ocr, s5_field_extract, s6_metrology, s7_dossier

_VISION_STAGE_NAMES = ("s1_frame_quality", "s2_geometry_detect",
                       "s3_calibration")
_VISION_CACHE: dict = {}


def _pda_from_options(shape_hint: str, options: dict) -> tuple:
    """Rule 7(4) PDA from inspector-supplied dimensions — pure logic.

    Mirrors s3_calibration.compute_pda, which CANNOT be imported on B1
    device builds (its module pulls cv2). The formulas live in
    rules/table1_fonts (stdlib) — the law stays in one place, only the
    caller differs."""
    from .config import PDA_SANITY_CM2
    from .rules.table1_fonts import (pda_cylindrical_cm2, pda_other_cm2,
                                     pda_rectangular_cm2)
    opts = options or {}
    h = opts.get("package_height_cm")
    w = opts.get("package_width_cm")
    d = opts.get("package_diameter_cm")
    total = opts.get("total_surface_cm2")
    shape = (shape_hint or "").lower()
    if shape in ("cylindrical", "bottle"):
        if h and d:
            return pda_cylindrical_cm2(h, d), "inspector-dims"
        return None, ""
    if shape in ("rectangular", "pouch") and h and w:
        return pda_rectangular_cm2(h, w), "inspector-dims"
    if total:
        return pda_other_cm2(total), "inspector-dims"
    if h and w:                        # shape unknown, flat dims given
        return pda_rectangular_cm2(h, w), "inspector-dims"
    return None, ""



def _load_vision_stages() -> dict:
    """Import s1/s2/s3 lazily: absent vision deps (B1 device build) yield
    None instead of an ImportError at module-import time."""
    for name in _VISION_STAGE_NAMES:
        if name not in _VISION_CACHE:
            try:
                _VISION_CACHE[name] = importlib.import_module(
                    f"netra_core.stages.{name}")
            except Exception:
                _VISION_CACHE[name] = None
    return _VISION_CACHE


def __getattr__(name: str):
    """PEP 562 — _STAGES_IN_ORDER resolves lazily (then caches) so
    importing this module never requires cv2. Tests may patch the module
    attribute directly; this fires only while it is unset."""
    if name == "_STAGES_IN_ORDER":
        v = _load_vision_stages()
        order = (("s1_frame_quality", v["s1_frame_quality"]),
                 ("s2_geometry_detect", v["s2_geometry_detect"]),
                 ("s3_calibration", v["s3_calibration"]),
                 ("s4_ocr", s4_ocr),
                 ("s5_field_extract", s5_field_extract),
                 ("s6_metrology", s6_metrology),
                 ("s7_dossier", s7_dossier))
        globals()["_STAGES_IN_ORDER"] = order
        return order
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _decode(image_b64: str) -> tuple:
    """-> (raw_bytes, BGR frame). Raises ValueError on any failure.
    cv2/numpy import lazily (B1 device builds have neither)."""
    import cv2
    import numpy as np
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"invalid base64 image: {e}") from e
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("bytes are not a decodable JPEG/PNG")
    return raw, img


def decode_image(image_b64: str):
    """Public wrapper for future stages / tests."""
    return _decode(image_b64)[1]


def _remap_evidence(ctx: PipelineContext, calib) -> None:
    """After Stage 5 measured font heights in the corrected frame, map
    token and field bboxes back to crop-frame pixel space."""
    if calib is None or calib.map_x is None:
        return
    ctx.tokens = [replace(t, bbox=calib.bbox_to_source(t.bbox))
                  if t.bbox is not None else t
                  for t in ctx.tokens]
    for key, fv in list(ctx.fields.items()):
        if fv.bbox is not None:
            ctx.fields[key] = replace(fv, bbox=calib.bbox_to_source(fv.bbox))


def _offset_evidence(ctx: PipelineContext, origin: tuple) -> None:
    """Stage 2 cropped the frame; shift evidence bboxes back to
    submitted-image pixel space (contract section 5)."""
    if origin == (0, 0):
        return
    dx, dy = origin
    ctx.tokens = [replace(t, bbox=replace(t.bbox, x=t.bbox.x + dx,
                                          y=t.bbox.y + dy))
                  if t.bbox is not None else t
                  for t in ctx.tokens]
    for key, fv in list(ctx.fields.items()):
        if fv.bbox is not None:
            ctx.fields[key] = replace(
                fv, bbox=replace(fv.bbox, x=fv.bbox.x + dx, y=fv.bbox.y + dy))


def _record_result(ctx: PipelineContext, result: dict) -> None:
    """Ledger write for COMPLETED scans. A ledger failure must never
    destroy a completed audit result — but it is surfaced in prompts so
    the inspector is aware."""
    if result["verdict"] not in ("PASS", "VIOLATION"):
        return
    try:
        db = queue_db.get_db()
        db.record_scan(ctx.image_id, result["verdict"],
                       image_sha256=ctx.image_sha256 or None,
                       dossier_sha256=ctx.dossier_sha256,
                       dossier_path=ctx.dossier_path or None)
        db.update_result(ctx.image_id, result)
    except Exception:
        # Never destroy a completed audit — but never hide the failure
        # either: the inspector is told the evidence was NOT stored.
        try:
            result["quality"].setdefault("prompts", []).append(
                "Audit calculated, but the evidence ledger write failed — "
                "do not close this inspection; rescan or report the device")
        except Exception:
            pass


def run_scan(request: ScanRequest) -> dict:
    """Image path (full-stack builds). Always contract JSON."""
    ctx = PipelineContext(
        shape_hint=request.shape_hint,
        meta={"gps": request.gps, "device": request.device,
              "options": request.options},
    )
    if request.captured_utc:
        ctx.captured_utc = request.captured_utc

    stages = getattr(sys.modules[__name__], "_STAGES_IN_ORDER")
    missing = [n for n, m in stages if m is None]
    if missing:
        return error_result(
            "STAGE_FAILURE",
            "vision stack not installed on this build ("
            f"{', '.join(missing)}) — use the scan_tokens path (B1)",
            stage=missing[0], request=request)

    try:
        raw, img = _decode(request.image_b64)
    except (ValueError, ImportError) as e:
        return error_result("DECODE_ERROR", str(e), request=request)

    ctx.image_sha256 = hashlib.sha256(raw).hexdigest()
    if request.image_sha256 and request.image_sha256.lower() != ctx.image_sha256:
        return error_result("BAD_REQUEST",
                            "image_sha256 mismatch — image altered in transit",
                            request=request)

    calib = None
    crop_origin = (0, 0)
    source_img = img                  # evidence crops + hash chain source
    for name, module in stages:
        try:
            if name == "s1_frame_quality":
                report = module.run(ctx, img)
                if not report.ok:
                    return result_from_context(ctx, request=request)
            elif name == "s2_geometry_detect":
                geo = module.run(ctx, img, options=request.options)
                if geo.crop is not None:
                    crop_origin = geo.origin
                    img = geo.crop          # package (+ card) feeds s3/s4
            elif name == "s3_calibration":
                calib = module.run(ctx, img, options=request.options)
                if not calib.ok:
                    return result_from_context(ctx, request=request)
                if calib.frame is not None:
                    img = calib.frame        # corrected frame feeds Stage 4
            elif name == "s4_ocr":
                module.run(ctx, frame_bgr=img)
            elif name == "s5_field_extract":
                module.run(ctx)
                _remap_evidence(ctx, calib)
                _offset_evidence(ctx, crop_origin)
            elif name == "s6_metrology":
                module.run(ctx, options=request.options)
            elif name == "s7_dossier":
                module.run(ctx, source_frame=source_img,
                           options=request.options)
            else:
                module.run(ctx)
        except Exception as e:              # contract section 9 — in-band
            return error_result("INTERNAL",
                                f"{name}: {type(e).__name__}: {e}",
                                stage=name, scan_id=ctx.image_id,
                                request=request)

    result = result_from_context(ctx, request=request)
    _record_result(ctx, result)
    return result


# ------------------------------------------------------ B1 device path
def run_scan_tokens(request) -> dict:
    """Contract v1.3 scan_tokens: OCR line tokens + optional quality /
    geometry / glyphs / image from the platform, evaluated by the full
    statutory engine. Identical 17-key ScanResult; identical ledger,
    dossier and signing semantics; zero vision dependencies."""
    ctx = PipelineContext(
        shape_hint=request.shape_hint,
        meta={"gps": request.gps, "device": request.device,
              "options": request.options},
    )
    if request.captured_utc:
        ctx.captured_utc = request.captured_utc

    source_frame = None
    if request.image_b64:
        try:
            raw = base64.b64decode(request.image_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            return error_result("DECODE_ERROR", f"invalid base64 image: {e}",
                                request=request)
        try:
            from PIL import Image
            with Image.open(io.BytesIO(raw)) as im:
                source_frame = im.convert("RGB")
        except Exception as e:
            return error_result("DECODE_ERROR",
                                f"undecodable image: {e}", request=request)
        ctx.image_sha256 = hashlib.sha256(raw).hexdigest()
        if request.image_sha256 and \
                request.image_sha256.lower() != ctx.image_sha256:
            return error_result(
                "BAD_REQUEST",
                "image_sha256 mismatch — image altered in transit",
                request=request)

    q = dict(request.quality or {})
    ctx.quality = {
        "ok": q.get("ok"),
        "laplacian_var": q.get("laplacian_var"),
        "glare_pct": q.get("glare_pct"),
        "prompts": list(q.get("prompts") or []),
        "glare_bbox": q.get("glare_bbox"),
    }
    if q.get("ok") is False:
        # mirror the s1 gate: rejected frame -> RETRY with guidance
        if not ctx.quality["prompts"]:
            ctx.quality["prompts"].append(
                "Frame rejected by the device quality gate — steady the "
                "camera and rescan")
        return result_from_context(ctx, request=request)

    g = dict(request.geometry or {})
    if not ctx.shape_hint and g.get("shape"):
        ctx.shape_hint = g["shape"]
    ctx.mm_per_px = g.get("mm_per_px")
    ctx.pda_cm2 = g.get("pda_cm2")
    ctx.pda_method = str(g.get("pda_method") or "")
    if ctx.pda_cm2 is None:
        pda, method = _pda_from_options(ctx.shape_hint, request.options)
        if pda is not None and (PDA_SANITY_CM2[0] <= pda <= PDA_SANITY_CM2[1]):
            ctx.pda_cm2 = round(float(pda), 2)
            ctx.pda_method = method
    ctx.shape_detected = str(g.get("shape_detected") or "")
    ctx.rois = [{"roi": r.get("roi"),
                 "bbox": BBox.from_list(r["bbox"]),
                 "conf": float(r.get("conf") or 0.0)}
                for r in (g.get("rois") or [])]
    ctx.glyphs = list(request.glyphs)

    s4_ocr.run(ctx, tokens=list(request.tokens))
    s5_field_extract.run(ctx)
    s6_metrology.run(ctx, options=request.options)
    s7_dossier.run(ctx, source_frame=source_frame,
                   options=request.options)

    result = result_from_context(ctx, request=request)
    _record_result(ctx, result)
    return result


# ------------------------------------------------------- signing handshake
def _sig_response(scan_id, accepted, sig_status, verified, error=None):
    return {"schema_version": SCHEMA_VERSION, "scan_id": scan_id or "",
            "accepted": accepted, "sig_status": sig_status,
            "verified": verified, "error": error}


def attach_signature(scan_id, signature, cert_pem) -> dict:
    """Contract section 8: the platform returns its ECDSA P-256 signature
    over crypto.sign_payload(scan_id, dossier_sha256). Verifies with the
    certificate's public key when `cryptography` is available; stores and
    flips the ledger row to signed. One implementation, two transports."""
    if (not isinstance(scan_id, str) or not scan_id
            or not isinstance(signature, str) or not signature
            or not isinstance(cert_pem, str) or not cert_pem):
        return _sig_response("", False, "pending", False,
                             {"code": "BAD_REQUEST",
                              "message": "scan_id, signature, cert_pem "
                                         "are required strings"})
    row = queue_db.get_db().get_scan(scan_id)
    if row is None:
        return _sig_response(scan_id, False, "pending", False,
                             {"code": "NOT_FOUND",
                              "message": f"no completed scan {scan_id}"})
    if row["sig_status"] == "signed":
        return _sig_response(scan_id, False, "signed", bool(row["sig_verified"]),
                             {"code": "ALREADY_SIGNED",
                              "message": "scan already carries a signature"})
    if not row["dossier_sha256"]:
        return _sig_response(scan_id, False, "pending", False,
                             {"code": "NO_DOSSIER",
                              "message": "scan has no dossier to sign"})
    verified, err = crypto.verify_signature(
        scan_id, row["dossier_sha256"], signature, cert_pem)
    if err is not None:
        return _sig_response(scan_id, False, "pending", False,
                             {"code": "VERIFY_FAILED", "message": err})
    queue_db.get_db().attach_signature(scan_id, signature, cert_pem, verified)
    return _sig_response(scan_id, True, "signed", verified, None)


# ------------------------------------------------------------------ demo path
def _tok(x, y, w, h, text, conf=0.97, engine="mlkit"):
    return OCRToken(text=text, bbox=BBox(x, y, w, h),
                    conf=conf, engine=engine, lang="en")


# Simulated ML Kit line tokens for the demo pouch label (800x800 frame).
_DEMO_TOKENS = (
    _tok(200, 60, 420, 60, "Instant Masala Noodles", 0.98),
    _tok(120, 340, 150, 30, "Net Quantity:", 0.96),
    _tok(280, 340, 90, 30, "70 gms", 0.97),
    _tok(120, 388, 60, 40, "MRP", 0.97),
    _tok(185, 388, 110, 40, "₹ 14.00", 0.98),
    _tok(120, 432, 160, 30, "Unit Sale Price", 0.95),
    _tok(285, 432, 130, 30, "₹ 0.35 / g", 0.96),
    _tok(40, 560, 70, 26, "MFG", 0.97),
    _tok(115, 560, 90, 26, "08/2026", 0.98),
    _tok(40, 600, 300, 26, "Imported by: Global Foods,", 0.95),
    _tok(40, 630, 180, 26, "Mumbai 400001", 0.96),
    _tok(40, 700, 160, 26, "Made in PRC", 0.96),
    _tok(40, 740, 300, 26, "Consumer Care: Global Foods,", 0.94),
    _tok(40, 770, 220, 26, "Tel: 1800-123-4567", 0.95),
)


def _tokens_from_label(label: dict) -> list:
    """Legacy demo input: raw field strings -> one token per line."""
    out, y = [], 40
    for key in ("product_name", "net_qty", "mrp", "usp", "mfg_date",
                "mfg_address", "origin", "consumer_care"):
        text = label.get(key)
        if text:
            out.append(_tok(40, y, 380, 30, str(text), 0.95))
            y += 40
    return out


def _demo_frame(tokens):
    """Render demo tokens onto a synthetic label image. ASCII-safe: the
    rupee sign draws as 'Rs'. Desktop-only (needs cv2 at call time)."""
    import cv2
    import numpy as np
    frame = np.full((800, 800, 3), 252, np.uint8)
    for t in tokens:
        x, y, w, h = t.bbox.to_list()
        text = t.text.replace("₹", "Rs")
        scale = max(0.4, h / 34.0)
        cv2.putText(frame, text, (x + 2, y + h - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, (35, 35, 35),
                    max(1, h // 20), cv2.LINE_AA)
    return frame


def run_demo_scan(tokens=None, label=None, options=None,
                  dossier: bool = False) -> dict:
    """Full statutory engine over injected OCR tokens (desktop demo)."""
    default_demo = tokens is None and label is None
    if tokens is None:
        tokens = _tokens_from_label(label) if label else list(_DEMO_TOKENS)

    ctx = PipelineContext(shape_hint="pouch")
    if default_demo:
        # the five planted SIH26034 traps (font height + PDA included)
        ctx.mm_per_px = 0.04
        ctx.pda_cm2 = 80.0            # Table-I band 2 -> 1.5 mm minimum
        ctx.pda_method = "demo"

    s4_ocr.run(ctx, tokens=tokens)
    s5_field_extract.run(ctx)
    s6_metrology.run(ctx, options=options)

    if dossier:
        import cv2
        frame = _demo_frame(tokens)
        ok, buf = cv2.imencode(".jpg", frame,
                               [cv2.IMWRITE_JPEG_QUALITY, 92])
        ctx.image_sha256 = hashlib.sha256(buf.tobytes()).hexdigest()
        ctx.meta = {"device": {"model": "NETRA desktop demo",
                               "os": sys.platform},
                    "gps": {"lat": 19.0760, "lon": 72.8777,
                            "source": "demo"}}
        s7_dossier.run(ctx, source_frame=frame, options=options)

    result = result_from_context(ctx)
    if dossier:
        _record_result(ctx, result)
    return result
