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
