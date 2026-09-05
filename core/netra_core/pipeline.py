"""NETRA pipeline orchestrator.

run_scan: stages in statutory order; the first unimplemented stage
short-circuits with a STAGE_FAILURE envelope (contract v1) — both
transports light up stage by stage as s2/s3/s7 land.

run_demo_scan: REAL Stage 5 + Stage 6 execution over injected OCR tokens
(the s4 dev-injection path). The demo label carries the five planted
SIH26034 traps; fields are extracted by the actual K-NN heuristics —
nothing is fabricated — and Rule 7 heights are derived from
bbox height x mm_per_px, exactly as live scans will be.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Optional

import cv2
import numpy as np

from .bridge.schema import ScanRequest, error_result, result_from_context
from .context import BBox, OCRToken, PipelineContext
from .stages import s1_frame_quality, s4_ocr, s5_field_extract, s6_metrology

# stage name -> runnable | None. Each None disappears as its stage lands.
_STAGES_IN_ORDER = (
    ("s1_frame_quality", s1_frame_quality),
    ("s2_geometry_detect", None),
    ("s3_calibration", None),
    ("s4_ocr", s4_ocr),
    ("s5_field_extract", s5_field_extract),
    ("s6_metrology", s6_metrology),
    ("s7_dossier", None),
)


def _decode(image_b64: str) -> tuple:
    """-> (raw_bytes, BGR frame). Raises ValueError on any failure."""
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"invalid base64 image: {e}") from e
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("bytes are not a decodable JPEG/PNG")
    return raw, img


def decode_image(image_b64: str) -> np.ndarray:
    """Public wrapper for future stages / tests."""
    return _decode(image_b64)[1]


def run_scan(request: ScanRequest) -> dict:
    """The one entrypoint behind both transports. Always contract JSON."""
    ctx = PipelineContext(
        shape_hint=request.shape_hint,
        meta={"gps": request.gps, "device": request.device,
              "options": request.options},
    )
    if request.captured_utc:
        ctx.captured_utc = request.captured_utc

    try:
        raw, img = _decode(request.image_b64)
    except ValueError as e:
        return error_result("DECODE_ERROR", str(e), request=request)

    ctx.image_sha256 = hashlib.sha256(raw).hexdigest()
    if request.image_sha256 and request.image_sha256.lower() != ctx.image_sha256:
        return error_result("BAD_REQUEST",
                            "image_sha256 mismatch — image altered in transit",
                            request=request)

    for name, module in _STAGES_IN_ORDER:
        if module is None:
            return result_from_context(
                ctx, request=request,
                error={"code": "STAGE_FAILURE",
                       "message": f"{name} not implemented yet",
                       "stage": name})
        if name == "s1_frame_quality":
            report = module.run(ctx, img)
            if not report.ok:
                return result_from_context(ctx, request=request)  # RETRY + prompts
        elif name == "s4_ocr":
            module.run(ctx, frame_bgr=img)
        elif name == "s6_metrology":
            module.run(ctx, options=request.options)
        else:
            module.run(ctx)             # uniform signature as stages land

    return result_from_context(ctx, request=request)


# ------------------------------------------------------------------ demo path
def _tok(x, y, w, h, text, conf=0.97, engine="mlkit"):
    return OCRToken(text=text, bbox=BBox(x, y, w, h),
                    conf=conf, engine=engine, lang="en")


# Simulated ML Kit line tokens for the demo pouch label (800x800 frame).
# Layout exercises every aggregation level: split anchor/value pairs (L2),
# inline tokens (L1), and a two-line address paragraph (L4).
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


def run_demo_scan(tokens=None, label=None, options=None) -> dict:
    """Full statutory engine over injected OCR tokens.

    Default tokens carry the five planted SIH26034 traps; pass your own
    OCRToken list (or a legacy {field: raw} dict) to explore verdicts.
    """
    if tokens is None:
        tokens = _tokens_from_label(label) if label else list(_DEMO_TOKENS)

    ctx = PipelineContext(shape_hint="pouch")
    ctx.mm_per_px = 0.04          # demo metric scale (Stage 3 supplies the real one)
    ctx.pda_cm2 = 80.0            # Table-I band 2 -> 1.5 mm minimum
    ctx.pda_method = "demo"

    s4_ocr.run(ctx, tokens=tokens)
    s5_field_extract.run(ctx)
    s6_metrology.run(ctx, options=options)
    return result_from_context(ctx)
