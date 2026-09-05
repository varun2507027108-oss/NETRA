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
            if not any(ch.isalnum() for ch in text):
                continue                       # punctuation noise
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
        return tokens

    return engine


def register(psm: int = 11, lang: str = "eng", **kwargs) -> None:
    """Register this adapter into Stage 4's engine registry."""
    from ..stages import s4_ocr
    if not available():
        raise RuntimeError(INSTALL_HINT)
    s4_ocr.register_engine("tesseract",
                           make_engine(psm=psm, lang=lang, **kwargs))
