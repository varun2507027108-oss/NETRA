"""Tesseract OCR adapter — the desktop/dev tier for Stage 4.

Registers into netra_core.stages.s4_ocr's engine registry under the
"tesseract" tier so REAL PHOTOGRAPHS run end-to-end off-device (no ML
Kit): calibrate (s3) -> OCR (this adapter) -> extract (s5) -> judge
(s6). Production Android uses ML Kit via the Chaquopy bridge; this
adapter never ships on device.

Requirements (optional extra `ocr`):
    pip install netra-core[ocr]                  # pytesseract
    system binary:
      Windows : winget install UB-Mannheim.TesseractOCR
      Linux   : sudo apt install tesseract-ocr [tesseract-ocr-hin]
      macOS   : brew install tesseract [tesseract-lang]
    TESSERACT_CMD env var overrides the binary path (stale shells).

Word-level tokens (Tesseract TSV) feed Stage 5's line clustering and
right-ray aggregation directly. Images are resampled toward
target_long_side — Tesseract accuracy collapses on small glyphs — and
token bboxes are mapped back to the input frame's coordinate space.
The ArUco fiducial in frame may yield a few garbage tokens; s5's
typed-parse gating and anchor matching tolerate them (they anchor as
nothing and parse as nothing statutory).
"""
from __future__ import annotations

import os

import cv2
import numpy as np

from ..context import BBox, OCRToken

try:
    import pytesseract
    from pytesseract import Output
    HAVE_PYTESSERACT = True
except Exception:
    HAVE_PYTESSERACT = False


INSTALL_HINT = (
    "tesseract OCR is not usable on this machine:\n"
    "  pip install netra-core[ocr]                  (python package)\n"
    "  winget install UB-Mannheim.TesseractOCR     (windows binary)\n"
    "  sudo apt install tesseract-ocr              (linux binary)\n"
    "  or set TESSERACT_CMD=<path to tesseract.exe>"
)


def _merge_line_tokens(tokens):
    """Word tokens -> LINE tokens.

    Stage 5's anchor vocabulary is line-level ("Net Quantity", "Unit Sale
    Price", "Mfd. by" must appear inside ONE token's text to anchor);
    Tesseract emits words. Group words into geometric lines (vertical
    overlap >= 0.4 with the growing line — ML Kit line semantics) so every
    engine registered into s4 normalizes to the same token granularity.
    """
    if not tokens:
        return []
    lines: list = []
    for t in sorted(tokens, key=lambda t: (t.bbox.y, t.bbox.x)):
        placed = False
        for line in lines:
            ys = [o.bbox.y for o in line]
            y2s = [o.bbox.y2 for o in line]
            lh = max(y2s) - min(ys)
            inter = min(max(y2s), t.bbox.y2) - max(min(ys), t.bbox.y)
            if inter > 0 and inter / max(1, min(lh, t.bbox.h)) >= 0.4:
                line.append(t)
                placed = True
                break
        if not placed:
            lines.append([t])
    merged = []
    for line in lines:
        line.sort(key=lambda t: t.bbox.x)
        merged.append(OCRToken(
            text=" ".join(t.text for t in line),
            bbox=BBox(min(t.bbox.x for t in line),
                      min(t.bbox.y for t in line),
                      max(t.bbox.x2 for t in line) - min(t.bbox.x for t in line),
                      max(t.bbox.y2 for t in line) - min(t.bbox.y for t in line)),
            conf=round(min(t.conf for t in line), 3),
            engine=line[0].engine, lang=line[0].lang))
    return merged


def _apply_cmd_override() -> None:
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def available() -> bool:
    """pytesseract importable AND the tesseract binary responds."""
    if not HAVE_PYTESSERACT:
        return False
    try:
        _apply_cmd_override()
        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def make_engine(psm: int = 11, lang: str = "eng", min_conf: float = 35.0,
                target_long_side: int = 2400):
    """Build a Stage-4 engine: callable(frame_bgr) -> list[OCRToken].

    psm 11 (sparse text) suits scattered declaration blocks; try psm 6
    for dense single-block labels. lang="eng+hin" adds Devanagari
    (requires the hin traineddata). Bounding boxes are returned in the
    coordinate space of the frame passed in.
    """

    def engine(frame_bgr: np.ndarray):
        from ..context import BBox, OCRToken
        if frame_bgr is None or frame_bgr.size == 0:
            return []
        _apply_cmd_override()
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        scale = float(target_long_side) / float(max(h, w))
        scale = max(0.5, min(4.0, scale))
        if abs(scale - 1.0) > 0.02:
            interp = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
            gray = cv2.resize(gray, (int(round(w * scale)),
                                     int(round(h * scale))),
                              interpolation=interp)
        data = pytesseract.image_to_data(
            gray, lang=lang, config=f"--psm {psm}",
            output_type=Output.DICT)
        tokens = []
        for i in range(len(data.get("text", []))):
            text = (data["text"][i] or "").strip()
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                continue
            if not text or conf < min_conf:
                continue
            if not any(ch.isalnum() or ch == "/" for ch in text):
                continue    # punctuation noise — but '/' survives: the USP
                            # declaration ("Rs 0.25 / g") needs the slash to
                            # parse; dropping it manufactures a false 6(11)
            cw, ch = int(data["width"][i]), int(data["height"][i])
            if cw <= 0 or ch <= 0:
                continue
            tokens.append(OCRToken(
                text=text,
                bbox=BBox(int(round(data["left"][i] / scale)),
                          int(round(data["top"][i] / scale)),
                          max(1, int(round(cw / scale))),
                          max(1, int(round(ch / scale)))),
                conf=round(min(1.0, conf / 100.0), 3),
                engine="tesseract", lang=lang))
        return _merge_line_tokens(tokens)

    return engine


def register(psm: int = 11, lang: str = "eng", **kwargs) -> None:
    """Register this adapter into Stage 4's engine registry."""
    from ..stages import s4_ocr
    if not available():
        raise RuntimeError(INSTALL_HINT)
    s4_ocr.register_engine("tesseract",
                           make_engine(psm=psm, lang=lang, **kwargs))
