"""s2_roi_merge.py — merge ML ROI boxes into the s2 geometry stage.

Pure stdlib. Consumes roi_boxes produced on-device by NetraYolo.kt (or by
netra_core.contrib.yolo_provider on the desktop bridge) in CAPTURE space —
the 1600px resize-once frame that frame_bgr and every downstream stage
already operate in (coordinate-space rule: never violated, no rescaling).

Emits ctx.rois entries in the exact dict shape s2 already produces:
{"roi": <LABEL>, "bbox": BBox, "conf": float} — downstream consumers see a
uniform structure regardless of detection source.

BBox (netra_core.context) is int-typed by contract; ML boxes are rounded
to the nearest pixel on merge — sub-pixel precision is irrelevant for ROI
anchoring, and classical boxes are already integral.

Merge policy (deterministic):
  - ML boxes (already conf-gated + NMS'd by the decoder) are authoritative
    for their labels; emitted sorted by score desc, ties by label (stable).
  - Classical rois whose label no ML box covers are appended in their
    original order (fallback chain: ML -> classical).
  - Empty/None roi_boxes -> classical rois returned unchanged (copy).

Never imports netra_core.contrib — boxes arrive over the wire from the
device, or are injected by the bridge upstream. ZERO statutory logic.
"""

from __future__ import annotations

import math

from ..context import BBox

REQUIRED_LABELS = ("PACKAGE", "PDP", "PRICE", "BARCODE", "BOP")


def _validate(box):
    try:
        label = box["label"]
        score = float(box["score"])
        x = float(box["x"])
        y = float(box["y"])
        w = float(box["w"])
        h = float(box["h"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"malformed roi_box: {box!r}") from exc
    if label not in REQUIRED_LABELS:
        raise ValueError(f"unknown roi label: {label!r}")
    if not (0.0 <= score <= 1.0):
        raise ValueError(f"roi score out of [0,1]: {score}")
    if w <= 0.0 or h <= 0.0:
        raise ValueError(f"non-positive roi size: {w}x{h}")
    return label, score, x, y, w, h


def merge_roi_boxes(classical_rois, roi_boxes):
    """Merge wire-format roi_boxes into s2's ctx.rois list shape."""
    if not roi_boxes:
        return list(classical_rois or [])

    ml = []
    for box in roi_boxes:
        label, score, x, y, w, h = _validate(box)
        ml.append({"roi": label,
                   "bbox": BBox(x=int(round(x)), y=int(round(y)),
                                w=int(round(w)), h=int(round(h))),
                   "conf": score})
    ml.sort(key=lambda r: (-r["conf"], r["roi"]))

    covered = {r["roi"] for r in ml}
    out = list(ml)
    for r in classical_rois or []:
        if r.get("roi") not in covered:
            out.append(r)
    return out


MAX_ROI_BOXES = 64  # wire guard; the decoder already caps per-class


def validate_roi_boxes(roi_boxes, frame_w, frame_h):
    """Wire-format validation + normalization for scan_tokens v1.4.0.

    Contract (CAPTURE space — the 1600px resize-once frame):
      roi_boxes absent/None/[] -> []  (classical fallback path)
      each box: {label, score, x, y, w, h}
        label in REQUIRED_LABELS
        score float in [0.0, 1.0]
        x, y float — may slightly overshoot frame edges (letterbox
          inversion artefact) -> clamped, not an error
        w, h float, > 0 — non-positive size is a decoder bug -> error
      Boxes are clamped to [0, frame_w] x [0, frame_h]; boxes degenerate
      after clamping (fully outside the frame) are dropped silently.
      More than MAX_ROI_BOXES raises (runaway decoder guard).

    Returns a NEW list of normalized dicts. The bridge calls this at the
    scan_tokens boundary; s2's merge then sees only clean, in-frame data,
    so its strict validation fires solely on genuine decoder bugs.
    """
    if roi_boxes is None:
        return []
    if not isinstance(roi_boxes, (list, tuple)):
        raise ValueError("roi_boxes must be a list")
    if len(roi_boxes) > MAX_ROI_BOXES:
        raise ValueError(f"roi_boxes count {len(roi_boxes)} > {MAX_ROI_BOXES}")
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError(f"invalid frame dimensions {frame_w}x{frame_h}")

    out = []
    for box in roi_boxes:
        if not isinstance(box, dict):
            raise ValueError(f"roi_box must be an object: {box!r}")
        try:
            label = box["label"]
            score = float(box["score"])
            x = float(box["x"])
            y = float(box["y"])
            w = float(box["w"])
            h = float(box["h"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed roi_box: {box!r}") from exc
        if label not in REQUIRED_LABELS:
            raise ValueError(f"unknown roi label: {label!r}")
        if not (math.isfinite(score) and 0.0 <= score <= 1.0):
            raise ValueError(f"roi score out of [0,1]: {score}")
        for name, v in (("x", x), ("y", y), ("w", w), ("h", h)):
            if not math.isfinite(v):
                raise ValueError(f"roi {name} not finite: {v}")
        if w <= 0.0 or h <= 0.0:
            raise ValueError(f"non-positive roi size: {w}x{h}")

        cx = min(max(x, 0.0), float(frame_w))
        cy = min(max(y, 0.0), float(frame_h))
        cw = min(w, float(frame_w) - cx)
        ch = min(h, float(frame_h) - cy)
        if cw <= 0.0 or ch <= 0.0:
            continue  # fully outside the frame — drop, not an error
        out.append({"label": label, "score": score,
                    "x": cx, "y": cy, "w": cw, "h": ch})
    return out
