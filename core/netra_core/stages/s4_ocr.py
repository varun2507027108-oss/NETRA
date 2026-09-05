"""Stage 4 — adaptive 3-tier hybrid OCR router (registry + dev injection).

Engines register via register_engine() and run in TIER_ORDER; the first
engine that yields tokens WINS (an engine that raises or yields nothing
falls through to the next tier). Per-ROI script/confidence routing —
the full hybrid design — lands with real ML Kit + IndicPhotoOCR
integration on device; the router surface below is frozen now.

  tier 1  "mlkit"      Google ML Kit v2, on-device via the Chaquopy Java
                       bridge (Latin + Devanagari, sub-30 ms)
  tier 1  "tesseract"  DESKTOP/DEV ONLY — Latin (eng), optional
                       Devanagari (eng+hin), so photographs run
                       end-to-end off-device; never ships on Android
  tier 2  "indic"      IndicPhotoOCR (Bhashini-IITJ scene-text model)
  tier 3  "bhashini"   ULCA cloud fallback (connectivity-gated, async)

Engine contract: callable(frame_bgr) -> list[OCRToken].

With no engines registered and no injected tokens the stage yields zero
tokens and the pipeline degrades to a contract RETRY — never a crash.
Dev/test paths inject tokens directly (run_demo_scan).
"""
from __future__ import annotations

import time

from ..context import PipelineContext

TIER_ORDER = ("mlkit", "tesseract", "indic", "bhashini")

_ENGINES: dict = {}


def register_engine(name: str, engine) -> None:
    if name not in TIER_ORDER:
        raise ValueError(f"unknown OCR tier {name!r}; "
                         f"expected one of {TIER_ORDER}")
    _ENGINES[name] = engine


def registered_engines() -> tuple:
    return tuple(n for n in TIER_ORDER if n in _ENGINES)


def run(ctx: PipelineContext, frame_bgr=None, tokens=None) -> list:
    t0 = time.perf_counter()
    if tokens is not None:                      # dev / test injection
        ctx.tokens = list(tokens)
    else:
        ctx.tokens = []
        for name in TIER_ORDER:
            engine = _ENGINES.get(name)
            if engine is None or frame_bgr is None:
                continue
            try:
                produced = engine(frame_bgr)
            except Exception:
                continue                        # engine down -> next tier
            if produced:
                ctx.tokens = list(produced)     # first tier with tokens wins
                break
    ms = (time.perf_counter() - t0) * 1000.0
    # zero tokens on a real scan = "no text decoded" -> RETRY — and the
    # inspector must be TOLD (contract 4.1/9: every RETRY carries guidance;
    # enforced by netra_core.qa.contract)
    if not ctx.tokens and tokens is None:
        ctx.quality.setdefault("prompts", []).append(
            "No text decoded — move closer, steady the frame, check lighting")
    ctx.add_stage("s4_ocr", bool(ctx.tokens), ms)
    return ctx.tokens
