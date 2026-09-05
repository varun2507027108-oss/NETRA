import numpy as np
import pytest

pytest.importorskip("cv2")

from netra_core.context import BBox, OCRToken, PipelineContext  # noqa: E402
from netra_core.stages import s4_ocr                             # noqa: E402


def _tok(engine):
    return OCRToken(text="x", bbox=BBox(1, 1, 2, 2), conf=1.0, engine=engine)


def _frame():
    return np.zeros((10, 10, 3), np.uint8)


def test_first_engine_wins(monkeypatch):
    monkeypatch.setitem(s4_ocr._ENGINES, "mlkit", lambda f: [_tok("mlkit")])
    monkeypatch.setitem(s4_ocr._ENGINES, "tesseract",
                        lambda f: [_tok("tesseract")] * 3)
    ctx = PipelineContext()
    toks = s4_ocr.run(ctx, frame_bgr=_frame())
    assert [t.engine for t in toks] == ["mlkit"]
    assert ctx.stages[-1].ok


def test_failing_engine_falls_to_next_tier(monkeypatch):
    def boom(f):
        raise RuntimeError("engine down")
    monkeypatch.setitem(s4_ocr._ENGINES, "mlkit", boom)
    monkeypatch.setitem(s4_ocr._ENGINES, "tesseract",
                        lambda f: [_tok("tesseract")])
    ctx = PipelineContext()
    toks = s4_ocr.run(ctx, frame_bgr=_frame())
    assert [t.engine for t in toks] == ["tesseract"]


def test_empty_engine_falls_to_next_tier(monkeypatch):
    monkeypatch.setitem(s4_ocr._ENGINES, "mlkit", lambda f: [])
    monkeypatch.setitem(s4_ocr._ENGINES, "tesseract",
                        lambda f: [_tok("tesseract")])
    ctx = PipelineContext()
    toks = s4_ocr.run(ctx, frame_bgr=_frame())
    assert [t.engine for t in toks] == ["tesseract"]


def test_no_engines_no_tokens_retry(monkeypatch):
    monkeypatch.setattr(s4_ocr, "_ENGINES", {})
    ctx = PipelineContext()
    toks = s4_ocr.run(ctx, frame_bgr=_frame())
    assert toks == [] and not ctx.stages[-1].ok


def test_ping_lists_registered_engines(monkeypatch):
    monkeypatch.setitem(s4_ocr._ENGINES, "tesseract", lambda f: [])
    from netra_core.bridge.schema import ping_payload
    assert "tesseract" in ping_payload()["capabilities"]["ocr_engines"]
