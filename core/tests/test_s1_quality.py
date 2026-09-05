import numpy as np
import pytest

pytest.importorskip("cv2")

from netra_core.context import Verdict            # noqa: E402
from netra_core.stages import s1_frame_quality    # noqa: E402


def test_flat_frame_is_blur():
    frame = np.full((480, 640, 3), 128, np.uint8)
    r = s1_frame_quality.analyse(frame)
    assert not r.ok and r.laplacian_var < 100.0


def test_sharp_noise_ok():
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 200, (480, 640, 3), dtype=np.uint8)
    r = s1_frame_quality.analyse(frame)
    assert r.ok and r.laplacian_var >= 100.0 and r.glare_pct == 0.0


def test_glare_detected_and_retry():
    rng = np.random.default_rng(1)
    frame = rng.integers(0, 120, (480, 640, 3), dtype=np.uint8)
    frame[100:160, 300:420] = 255
    r = s1_frame_quality.analyse(frame)
    assert r.glare_pct > 0 and not r.ok and r.prompts


def test_run_records_stage_and_drives_verdict():
    from netra_core.context import PipelineContext
    ctx = PipelineContext()
    s1_frame_quality.run(ctx, np.full((480, 640, 3), 128, np.uint8))
    assert ctx.stages[0].stage == "s1_frame_quality" and not ctx.stages[0].ok
    assert ctx.verdict is Verdict.RETRY
