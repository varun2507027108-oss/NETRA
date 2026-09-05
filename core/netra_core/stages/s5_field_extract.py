"""Stage 5 — anchor-to-value field extraction (deterministic K-NN, < 1 ms).

The LayoutLMv3 replacement promised by the SIH26034 spec: no model, no
400 MB footprint. Typed statutory fields are derived from OCR tokens via
escalating spatial aggregation:

  L1  the anchor token's own text            (inline: "MRP Rs 50.00 ...")
  L2  + tokens to the right on the same line (gap-limited greedy ray)
  L3  + the nearest aligned line below        (wrapped values)
  L4  paragraph growth — address & consumer-care blocks only: consume
      following lines while the vertical gap stays within
      PARA_GAP x anchor line height and no foreign anchor intervenes.

A candidate is accepted only when its typed parse succeeds (money, qty,
USP, date) or meets the text threshold — an unparsable "value" is never
attached. Everything is pure Python over token bboxes; no floats touch
statutory arithmetic (values stay Decimal via rules.parsers).

Known scope limits (deliberate, documented):
- net quantity requires an anchor word: anchor-less "200 g" pickup would
  swallow nutrition-panel weights ("Protein 20 g") until Stage 2 separates
  PDP / BOP ROIs;
- ctx.glyphs (Rule 7(3)) is NOT synthesized here — averaging token width
  across characters misattributes the 1/i/I/l statutory exemptions.
  Per-glyph segmentation lands with the vision pass;
- font heights = value bbox height x ctx.mm_per_px (Stage 3 supplies scale).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from ..context import BBox, FieldValue, OCRToken, PipelineContext
from ..rules.declarations import (
    FIELD_CONSUMER_CARE, FIELD_MFG_ADDRESS, FIELD_MFG_DATE, FIELD_MRP,
    FIELD_NET_QTY, FIELD_ORIGIN, FIELD_PRODUCT_NAME, FIELD_USP,
)
from ..rules.parsers import parse_date, parse_money, parse_quantity, parse_usp

# ---- spatial constants (in units of the anchor token's bbox height) --------
SAME_LINE_GAP = 2.0      # max inter-token x gap on the anchor's line
LINE_V_OVERLAP = 0.4     # vertical overlap ratio that groups tokens to a line
RIGHT_SLACK = 0.3        # tolerance for "to the right of the anchor"
BELOW_GAP = 1.5          # vertical gap for wrapped-value pickup (L3)
BELOW_H_OVERLAP = 0.2    # horizontal alignment required for L3
PARA_GAP = 1.3           # paragraph line spacing tolerance (L4)
PARA_H_OVERLAP = 0.15    # paragraph column alignment (L4)
PARA_MAX_LINES = 5       # statutory address blocks cap at 5 lines
MIN_ALPHA = 3            # product-name heuristic: min alphabetic chars
MIN_TEXT = 8             # "text"-mode acceptance: min raw length
PRODUCT_TOP_FRAC = 0.65  # product name expected in top 65% of token cloud

# ---- anchor vocabularies ----------------------------------------------------
_ANCHORS = {
    FIELD_NET_QTY: (
        r"\bnet\s*(?:quantity|qty|qnty|wt|weight|contents?)\b",
        r"^(?:quantity|qty)\b",
    ),
    FIELD_MRP: (
        r"\bm\.?\s*r\.?\s*p\.?\b",
        r"\bmax(?:imum)?\.?\s*retail\s*price\b",
    ),
    FIELD_USP: (
        r"\bunit\s*sale\s*price\b",
        r"\bu\.?\s*s\.?\s*p\.?\b",
    ),
    FIELD_MFG_DATE: (
        r"\bmfg\b", r"\bmfd\b",
        r"\bdate\s+of\s+(?:mfg|manufactur|pack)",
        r"\bmanufactur(?:ed|ing)\s+on\b",
        r"\bpack(?:ed|ing)\s+(?:on|date)\b",
    ),
    FIELD_ORIGIN: (
        r"country\s+of\s+origin", r"\borigin\b", r"\bmade\s+in\b",
        r"\bproduct\s+of\b", r"\bmanufactur(?:ed|ing)\s+in\b",
        r"\bpacked\s+in\b", r"\bassembled\s+in\b",
    ),
    FIELD_MFG_ADDRESS: (
        r"\bmfd\.?\s*by\b", r"\bmfg\.?\s*by\b", r"\bmkt?d\.?\s*by\b",
        r"\bmanufactur(?:ed|er|ers|ing)?\s*by\b", r"\bmanufacturers?\b",
        r"\bimport(?:er|ed|ers|ing)?\b", r"\bpacked\s+by\b",
        r"\bmarket(?:ed|er|ing)?\s*by\b",
    ),
    FIELD_CONSUMER_CARE: (
        r"consumer\s*(?:care|complaint|service|relation|grievance)",
        r"customer\s*(?:care|complaint|service)",
        r"grievance\s+officer", r"\bhelpline\b", r"toll\s*free",
    ),
}


@dataclass(frozen=True)
class FieldSpec:
    key: str
    accept: str        # 'qty' | 'money' | 'usp' | 'date' | 'text'
    paragraph: bool = False


SPECS = (
    FieldSpec(FIELD_NET_QTY, "qty"),
    FieldSpec(FIELD_MRP, "money"),
    FieldSpec(FIELD_USP, "usp"),
    FieldSpec(FIELD_MFG_DATE, "date"),
    FieldSpec(FIELD_ORIGIN, "text"),
    FieldSpec(FIELD_MFG_ADDRESS, "text", paragraph=True),
    FieldSpec(FIELD_CONSUMER_CARE, "text", paragraph=True),
)

_RX = {key: tuple(re.compile(p, re.IGNORECASE) for p in pats)
       for key, pats in _ANCHORS.items()}


# ------------------------------------------------------------------ geometry
def _v_overlap(a: BBox, b: BBox) -> float:
    inter = min(a.y2, b.y2) - max(a.y, b.y)
    return inter / max(1, min(a.h, b.h)) if inter > 0 else 0.0


def _h_overlap(a: BBox, b: BBox) -> float:
    inter = min(a.x2, b.x2) - max(a.x, b.x)
    return inter / max(1, min(a.w, b.w)) if inter > 0 else 0.0


def _union_box(boxes) -> BBox:
    xs = [b.x for b in boxes]
    ys = [b.y for b in boxes]
    x2s = [b.x2 for b in boxes]
    y2s = [b.y2 for b in boxes]
    return BBox(min(xs), min(ys), max(x2s) - min(xs), max(y2s) - min(ys))


def _cluster_lines(tokens):
    """Reading-order line clustering: token joins the current line when its
    vertical overlap with the line's union box >= LINE_V_OVERLAP."""
    lines = []
    for t in sorted(tokens, key=lambda t: (t.bbox.y, t.bbox.x)):
        if lines and _v_overlap(_union_box([x.bbox for x in lines[-1]]),
                                t.bbox) >= LINE_V_OVERLAP:
            lines[-1].append(t)
        else:
            lines.append([t])
    return lines


def _anchor_fields(token: OCRToken) -> tuple:
    keys = []
    for spec in SPECS:
        if any(rx.search(token.text) for rx in _RX[spec.key]):
            keys.append(spec.key)
    return tuple(keys)


# -------------------------------------------------------------- aggregation
def _right_of(anchor, line, anchor_map):
    """L2: tokens to the right of the anchor on its line, greedy while the
    inter-token gap stays within SAME_LINE_GAP line-heights. Stops at a
    foreign statutory anchor (compact labels share lines)."""
    out, prev_x2 = [], anchor.bbox.x2
    for t in sorted(line, key=lambda t: t.bbox.x):
        if t is anchor:
            continue
        if t.bbox.x < anchor.bbox.x2 - RIGHT_SLACK * anchor.bbox.h:
            continue                       # not to the right of the anchor
        if t.bbox.x - prev_x2 > SAME_LINE_GAP * anchor.bbox.h:
            break                          # ray ended (column/whitespace)
        if anchor_map.get(id(t)):
            break                          # another declaration starts here
        out.append(t)
        prev_x2 = max(prev_x2, t.bbox.x2)
    return out


def _below_line(anchor, lines, line_idx):
    """L3: the nearest line below the anchor, if close and aligned."""
    if line_idx + 1 >= len(lines):
        return []
    lb = _union_box([t.bbox for t in lines[line_idx + 1]])
    if lb.y - anchor.bbox.y2 > BELOW_GAP * anchor.bbox.h:
        return []
    if _h_overlap(anchor.bbox, lb) < BELOW_H_OVERLAP:
        return []
    return list(lines[line_idx + 1])


def _paragraph(anchor, first_line_right, lines, line_idx, anchor_map):
    """L4: grow the anchor's region downward while lines are close, roughly
    column-aligned, and free of foreign statutory anchors."""
    region = [anchor] + first_line_right
    i = line_idx + 1
    while i < len(lines) and (i - line_idx) < PARA_MAX_LINES:
        lb = _union_box([t.bbox for t in lines[i]])
        rb = _union_box([t.bbox for t in region])
        if lb.y - rb.y2 > PARA_GAP * anchor.bbox.h:
            break
        if _h_overlap(rb, lb) < PARA_H_OVERLAP:
            break
        if any(anchor_map.get(id(t)) for t in lines[i]):
            break                          # a new statutory block starts
        region.extend(lines[i])
        i += 1
    return region


def _aggregations(spec, anchor, lines, line_idx, anchor_map):
    right = _right_of(anchor, lines[line_idx], anchor_map)
    if spec.paragraph:
        return [_paragraph(anchor, right, lines, line_idx, anchor_map)]
    base = [anchor] + right
    cands = [[anchor]]
    if right:
        cands.append(base)
    below = _below_line(anchor, lines, line_idx)
    if below:
        cands.append(base + [t for t in below if not anchor_map.get(id(t))])
    return cands


# --------------------------------------------------------------- acceptance
def _accepts(mode: str, text: str) -> bool:
    if mode == "qty":
        return parse_quantity(text) is not None
    if mode == "money":
        return parse_money(text) is not None
    if mode == "usp":
        return parse_usp(text) is not None
    if mode == "date":
        return parse_date(text) is not None
    t = text.strip()
    return len(t) >= MIN_TEXT and sum(ch.isalpha() for ch in t) >= MIN_ALPHA


def _typed(key, raw):
    if key == FIELD_NET_QTY:
        q = parse_quantity(raw)
        return (q.value, q.unit) if q else (None, None)
    if key == FIELD_MRP:
        m = parse_money(raw)
        return (m, None) if m is not None else (None, None)
    if key == FIELD_USP:
        u = parse_usp(raw)
        return (u.value, u.unit) if u else (None, None)
    if key == FIELD_MFG_DATE:
        d = parse_date(raw)
        return (d, None) if d else (None, None)
    return None, None


# ------------------------------------------------------------------ extract
def extract_fields(tokens) -> dict:
    """Pure function: OCR tokens -> {field_key: FieldValue}. Deterministic."""
    toks = list(tokens)
    if not toks:
        return {}

    lines = _cluster_lines(toks)
    line_of = {id(t): i for i, line in enumerate(lines) for t in line}
    anchor_map = {id(t): _anchor_fields(t) for t in toks}
    fields: dict = {}
    used: set = set()

    def _text(cand):
        return " ".join(t.text for t in
                        sorted(cand, key=lambda t: (t.bbox.y, t.bbox.x)))

    for spec in SPECS:
        anchors = [t for t in toks if spec.key in anchor_map[id(t)]]
        anchors.sort(key=lambda t: (t.bbox.y, t.bbox.x))
        for anchor in anchors:
            if id(anchor) in used:
                continue
            for cand in _aggregations(spec, anchor, lines,
                                      line_of[id(anchor)], anchor_map):
                raw = _text(cand)
                if _accepts(spec.accept, raw):
                    value, unit = _typed(spec.key, raw)
                    fields[spec.key] = FieldValue(
                        raw=raw, value=value, unit=unit,
                        bbox=_union_box([t.bbox for t in cand]),
                        conf=round(min(t.conf for t in cand), 3))
                    used.update(id(t) for t in cand)
                    break
            if spec.key in fields:
                break

    # USP fallback: an unclaimed token that IS a unit-price expression
    if FIELD_USP not in fields:
        for t in sorted(toks, key=lambda t: (t.bbox.y, t.bbox.x)):
            if id(t) in used or anchor_map[id(t)]:
                continue
            u = parse_usp(t.text)
            if u is not None:
                fields[FIELD_USP] = FieldValue(
                    raw=t.text, value=u.value, unit=u.unit, bbox=t.bbox,
                    conf=round(float(t.conf), 3))
                used.add(id(t))
                break

    # product name: the tallest unconsumed, non-anchor token in the top
    # region of the label (PDP typography proxy for Rule 6(1)(b))
    if FIELD_PRODUCT_NAME not in fields:
        cloud = _union_box([t.bbox for t in toks])
        cands = [t for t in toks
                 if id(t) not in used and not anchor_map[id(t)]
                 and sum(ch.isalpha() for ch in t.text) >= MIN_ALPHA]
        top = [t for t in cands
               if t.bbox.cy <= cloud.y + PRODUCT_TOP_FRAC * cloud.h]
        pool = top or cands
        if pool:
            best = min(pool, key=lambda t: (-t.bbox.h, -(t.bbox.w * t.bbox.h),
                                            t.bbox.y, t.bbox.x))
            fields[FIELD_PRODUCT_NAME] = FieldValue(
                raw=best.text, value=None, unit=None, bbox=best.bbox,
                conf=round(float(best.conf), 3))

    return fields


def run(ctx: PipelineContext) -> dict:
    """Stage entrypoint: extract fields from ctx.tokens (set by Stage 4),
    measure font heights in mm when Stage 3 has supplied the metric scale."""
    t0 = time.perf_counter()
    fields = extract_fields(ctx.tokens)
    ctx.fields.update(fields)
    if ctx.mm_per_px:
        for key, fv in fields.items():
            if fv.bbox is not None:
                ctx.font_heights[key] = round(fv.bbox.h * ctx.mm_per_px, 3)
    ms = (time.perf_counter() - t0) * 1000.0
    ctx.add_stage("s5_field_extract", bool(fields), ms)
    return fields
