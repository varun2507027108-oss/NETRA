"""NETRA — shared data model (stdlib only).

Contract rule: this module and netra_core.rules must stay dependency-free
so the statutory engine runs identically in pytest, on desktop, and inside
Chaquopy on Android. Vision/OCR dependencies live in stages/, vision/, ocr/.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Verdict(str, Enum):
    PASS = "PASS"
    VIOLATION = "VIOLATION"
    RETRY = "RETRY"


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NA = "NA"   # not applicable (Rule 26 exemption / field absent)


@dataclass(frozen=True)
class BBox:
    """Axis-aligned box in pixel coordinates of the analysed frame."""
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int: return self.x + self.w
    @property
    def y2(self) -> int: return self.y + self.h
    @property
    def cx(self) -> float: return self.x + self.w / 2.0
    @property
    def cy(self) -> float: return self.y + self.h / 2.0

    def to_list(self) -> list:
        return [self.x, self.y, self.w, self.h]

    @classmethod
    def from_list(cls, seq) -> "BBox":
        x, y, w, h = (int(round(float(v))) for v in seq[:4])
        return cls(x, y, w, h)

    def iou(self, other: "BBox") -> float:
        ix = max(0, min(self.x2, other.x2) - max(self.x, other.x))
        iy = max(0, min(self.y2, other.y2) - max(self.y, other.y))
        inter = ix * iy
        union = self.w * self.h + other.w * other.h - inter
        return inter / union if union > 0 else 0.0


@dataclass(frozen=True)
class OCRToken:
    """One OCR text block. engine in {mlkit, indic, bhashini}."""
    text: str
    bbox: BBox
    conf: float = 1.0
    engine: str = "mlkit"
    lang: str = "en"


@dataclass(frozen=True)
class FieldValue:
    """A statutory field after parsing (produced by Stage 5)."""
    raw: str
    value: Any = None            # Decimal / date / str
    unit: Optional[str] = None   # canonical unit for quantities & USP
    bbox: Optional[BBox] = None
    conf: float = 0.0


@dataclass(frozen=True)
class Check:
    """One statutory finding. `rule` keys into netra_core.rules.citations."""
    rule: str
    status: CheckStatus
    message: str
    evidence: Optional[BBox] = None


@dataclass(frozen=True)
class StageResult:
    stage: str
    ok: bool
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class PipelineContext:
    """Everything one scan knows. Stages append; nothing mutates backwards."""
    image_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    captured_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    image_sha256: str = ""
    shape_hint: str = ""                    # rectangular|cylindrical|pouch|bottle|blister

    # filled by s1–s3
    quality: dict = field(default_factory=dict)
    mm_per_px: Optional[float] = None       # from ArUco + solvePnP
    pda_cm2: Optional[float] = None         # Rule 7(4)
    blown_or_molded: bool = False
    exemption: Optional[Any] = None         # rules.exemptions.Exemption

    # filled by s4–s5
    tokens: list = field(default_factory=list)        # list[OCRToken]
    fields: dict = field(default_factory=dict)        # str -> FieldValue
    font_heights: dict = field(default_factory=dict)  # field key -> mm

    # outputs
    checks: list = field(default_factory=list)        # list[Check]
    stages: list = field(default_factory=list)        # list[StageResult]
    dossier_sha256: Optional[str] = None

    def add_check(self, rule, status, message, evidence=None) -> Check:
        check = Check(rule=rule, status=CheckStatus(status),
                      message=message, evidence=evidence)
        self.checks.append(check)
        return check

    def add_stage(self, stage, ok, duration_ms=0.0, error=None) -> StageResult:
        res = StageResult(stage=stage, ok=ok, duration_ms=duration_ms, error=error)
        self.stages.append(res)
        return res

    @property
    def verdict(self) -> Verdict:
        if any(not s.ok for s in self.stages):
            return Verdict.RETRY
        if not self.checks:
            return Verdict.RETRY          # nothing evaluated — treat as retry
        if any(c.status is CheckStatus.FAIL for c in self.checks):
            return Verdict.VIOLATION
        return Verdict.PASS

    @property
    def failed_checks(self) -> list:
        return [c for c in self.checks if c.status is CheckStatus.FAIL]

    @property
    def total_ms(self) -> float:
        return sum(s.duration_ms for s in self.stages)
