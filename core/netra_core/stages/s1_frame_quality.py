"""Stage 1 — frame quality gate & glare filter (< 3 ms budget).

Pure OpenCV/numpy; no model, no I/O. Given a BGR frame, decides whether it
is worth running Stages 2–7 and produces repositioning prompts for the UI.
This run() signature is the pattern every subsequent stage will follow.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from ..config import GLARE_AREA_PCT_MAX, GLARE_PIXEL_MAX, LAPLACIAN_VAR_MIN
from ..context import BBox, PipelineContext


@dataclass(frozen=True)
class QualityReport:
    laplacian_var: float
    glare_pct: float
    ok: bool
    prompts: tuple = ()
    glare_bbox: BBox | None = None


def analyse(frame_bgr: np.ndarray) -> QualityReport:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    glare_mask = gray >= GLARE_PIXEL_MAX
    glare_pct = 100.0 * float(np.count_nonzero(glare_mask)) / glare_mask.size

    prompts, glare_bbox = [], None
    if lap_var < LAPLACIAN_VAR_MIN:
        prompts.append("Hold steady — frame is blurred")
    if glare_pct > GLARE_AREA_PCT_MAX:
        contours, _ = cv2.findContours(
            glare_mask.astype(np.uint8) * 255,
            cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
            glare_bbox = BBox(int(x), int(y), int(w), int(h))
            prompts.append("Tilt 10–15° to move glare off the label")

    return QualityReport(lap_var, glare_pct, not prompts, tuple(prompts), glare_bbox)


def run(ctx: PipelineContext, frame_bgr: np.ndarray) -> QualityReport:
    t0 = time.perf_counter()
    report = analyse(frame_bgr)
    ms = (time.perf_counter() - t0) * 1000.0
    ctx.quality = {
        "laplacian_var": report.laplacian_var,
        "glare_pct": report.glare_pct,
        "prompts": list(report.prompts),
        "glare_bbox": (report.glare_bbox.to_list()
                       if report.glare_bbox is not None else None),
    }
    ctx.add_stage("s1_frame_quality", report.ok, ms)
    return report
