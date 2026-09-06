"""Golden vectors for the planar scale estimator (audit finding #8).

Python: mm_per_px = marker_side / sqrt(contour_area). These vectors pin
the estimator against accidental formula drift; the Kotlin prepass is
held to the same vectors via the Tier 2 A/B bands (1-2%) documented in
ANDROID_INTEGRATION.md. A JUnit port of this table is the production
follow-up.
"""
import math

import cv2
import numpy as np
import pytest

from netra_core.stages.s3_calibration import _plane_transform


@pytest.mark.parametrize("corners,side_mm,expected", [
    (np.array([[220, 140], [420, 140], [420, 340], [220, 340]],
              dtype=np.float32), 40.0, 0.2),            # 200px frontoparallel
    (np.array([[100, 100], [200, 100], [200, 200], [100, 200]],
              dtype=np.float32), 40.0, 0.4),            # 100px
    (np.array([[230, 150], [410, 135], [425, 335], [215, 350]],
              dtype=np.float32), 40.0, 0.202547873),    # perspective / skewed
])
def test_mm_per_px_golden(corners, side_mm, expected):
    _C, _w, _h, mm_per_px = _plane_transform(corners, side_mm, (900, 700))
    assert mm_per_px == pytest.approx(expected, rel=1e-6)
    area = cv2.contourArea(corners)                     # estimator identity
    assert mm_per_px == pytest.approx(side_mm / math.sqrt(area), rel=1e-9)
