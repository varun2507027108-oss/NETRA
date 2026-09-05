"""Stage 4 — adaptive 3-tier hybrid OCR router (registry + dev injection).

Production tiers register via register_engine():
  tier 1  "mlkit"     Google ML Kit v2, 100% on-device, via the Chaquopy
                     Java bridge (Latin + Devanagari, sub-30 ms)
  tier 2  "indic"     IndicPhotoOCR (Bhashini-IITJ scene-text model) for
                     embossed / stylized regional scripts
  tier 3  "bhashini"  ULCA cloud fallback (connectivity-gated, async)

Engine contract: callable(frame_bgr) -> list[OCRToken]. Confidence and
Unicode-range routing policy lands with the real engines; the registry,
tier order, and the injection API are frozen NOW so Stage 5, the pipeline,
and the bridge are built against a stable surface.

With no engines registered (desktop default) the stage yields zero tokens
and the pipeline degrades to a contract RETRY — never a crash. Dev and
test paths inject tokens directly, which is how run_demo_scan exercises
Stages 5-6 with no vision stack at all.
"""
from __future__ import annotations

import time

from ..context import PipelineContext

TIER_ORDER = ("mlkit", "indic", "bhashini")

_ENGINES: dict = {}


def register_engine(name: str, engine) -> None:
    if name not in TIER_ORDER:
        raise ValueError(f"unknown OCR tier {name!r}; expected one of {TIER_ORDER}")
    _ENGINES[name] = engine


def registered_engines() -> tuple:
    return tuple(n for n in TIER_ORDER if n in _ENGINES)


def run(ctx: PipelineContext, frame_bgr=None, tokens=None) -> list:
    t0 = time.perf_counter()
    if tokens is not None:                      # dev / test injection
        ctx.tokens = list(tokens)
    else:
        out: list = []
        for name in TIER_ORDER:
            engine = _ENGINES.get(name)
            if engine is None or frame_bgr is None:
                continue
            out.extend(engine(frame_bgr))
        ctx.tokens = out
    ms = (time.perf_counter() - t0) * 1000.0
    # zero tokens on a real scan = "no text decoded" -> RETRY, rescan
    ctx.add_stage("s4_ocr", bool(ctx.tokens), ms)
    return ctx.tokens
