"""NETRA pipeline orchestrator (interim).

Runs every implemented stage in statutory order. The first stage that is
not yet implemented short-circuits with a STAGE_FAILURE error naming it —
so both transports already return contract-shaped RETRYs today and light
up stage by stage as s2-s5 and s7 land (add the import, replace the None).

run_demo_scan() fabricates the post-OCR state (Stage 4-5 output) so the
full s6 engine and the Flutter UI can be exercised with no vision stack.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Optional

import cv2
import numpy as np

from .bridge.schema import (ScanRequest, error_result, result_from_context)
from .context import BBox, FieldValue, PipelineContext
from .rules.parsers import parse_date, parse_money, parse_quantity, parse_usp
from .stages import s1_frame_quality, s6_metrology

# stage name -> runnable | None. Each None disappears as its stage lands.
_STAGES_IN_ORDER = (
    ("s1_frame_quality", s1_frame_quality),
    ("s2_geometry_detect", None),
    ("s3_calibration", None),
    ("s4_ocr", None),
    ("s5_field_extract", None),
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
                return result_from_context(ctx, request=request)   # RETRY + prompts
        elif name == "s6_metrology":
            module.run(ctx, options=request.options)
        else:
            module.run(ctx)          # uniform signature as stages land

    return result_from_context(ctx, request=request)


# ------------------------------------------------------------------ demo path
_DEMO_LABEL = {
    "product_name":  "Instant Masala Noodles",
    "net_qty":       "Net Quantity: 70 gms",         # trap: prohibited syntax
    "mrp":           "MRP ₹ 14.00",                  # trap: tax phrase missing
    "usp":           "Unit Sale Price ₹ 0.35 / g",   # trap: corrupted math
    "mfg_date":      "MFG 08/2026",
    "mfg_address":   "Imported by: Global Foods, Mumbai 400001",
    "origin":        "Made in PRC",                  # trap: ambiguous origin
    "consumer_care": "Consumer Care: Global Foods, Tel: 1800-123-4567",
}

_DEMO_BBOXES = {
    "product_name":  [40, 80, 360, 48],
    "net_qty":       [120, 340, 200, 34],
    "mrp":           [120, 388, 240, 34],
    "usp":           [120, 432, 220, 30],
    "mfg_date":      [40, 560, 140, 26],
    "mfg_address":   [40, 600, 420, 60],
    "origin":        [40, 660, 160, 26],
    "consumer_care": [40, 700, 430, 70],
}


def run_demo_scan(label: Optional[dict] = None,
                  options: Optional[dict] = None) -> dict:
    """Full statutory engine over a fabricated post-OCR state.

    Default label carries the five planted SIH26034 traps; pass your own
    dict of raw field strings to explore verdicts.
    """
    label = label or dict(_DEMO_LABEL)
    ctx = PipelineContext(shape_hint="pouch")
    fields = {}
    for k, v in label.items():
        raw = str(v)
        val = None
        unit = None
        if k == "mrp":
            val = parse_money(raw)
        elif k == "net_qty":
            q = parse_quantity(raw)
            if q is not None:
                val, unit = str(q.value), q.unit
        elif k == "usp":
            u = parse_usp(raw)
            if u is not None:
                val, unit = str(u.value), u.unit
        elif k == "mfg_date":
            val = parse_date(raw)
        bbox = BBox.from_list(_DEMO_BBOXES[k]) if k in _DEMO_BBOXES else None
        fields[k] = FieldValue(raw=raw, value=val, unit=unit, bbox=bbox)
    ctx.fields = fields
    ctx.pda_cm2 = 80.0          # Table-I band 2 -> 1.5 mm minimum
    ctx.pda_method = "demo"
    ctx.font_heights = {"net_qty": 1.2, "mrp": 1.6}   # trap: net qty too small

    s6_metrology.run(ctx, options=options)
    return result_from_context(ctx)
