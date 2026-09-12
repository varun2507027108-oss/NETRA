"""test_scan_tokens_roi.py — scan_tokens v1.4.0 roi_boxes wire contract.

Covers: schema acceptance + frame-required-if-boxes semantics, clamping at
the boundary, structural rejection, qa validator parity, and a full
round-trip of the recorded roi fixture through run_scan_tokens.
"""

import json
from pathlib import Path

import pytest

from netra_core.bridge.schema import scan_tokens_request_from_dict
from netra_core.pipeline import run_scan_tokens
from netra_core.qa import contract as qa

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "contract"

FRAME = {"w": 1600, "h": 1200}
GOOD_BOX = {"label": "PDP", "score": 0.9, "x": 10.0, "y": 20.0,
            "w": 100.0, "h": 50.0}


def _body(**over):
    base = {
        "tokens": [{"text": "MRP incl. of all taxes Rs 99.00",
                    "bbox": [10, 10, 200, 30], "conf": 0.9,
                    "engine": "mlkit", "lang": "en"}],
        "options": {},
    }
    base.update(over)
    return base


def test_accepts_roi_boxes_with_frame():
    req, err = scan_tokens_request_from_dict(
        _body(roi_boxes=[GOOD_BOX], roi_frame=FRAME))
    assert err is None and req is not None
    assert len(req.roi_boxes) == 1
    assert req.roi_frame == FRAME


def test_frame_without_boxes_is_fine():
    req, err = scan_tokens_request_from_dict(_body(roi_frame=FRAME))
    assert err is None and req.roi_boxes == ()


def test_boxes_without_frame_rejected():
    req, err = scan_tokens_request_from_dict(_body(roi_boxes=[GOOD_BOX]))
    assert req is None and err is not None


@pytest.mark.parametrize("box", [
    {"label": "NOPE", "score": 0.5, "x": 1.0, "y": 1.0, "w": 5.0, "h": 5.0},
    {"label": "PDP", "score": 1.5, "x": 1.0, "y": 1.0, "w": 5.0, "h": 5.0},
    {"label": "PDP", "score": 0.5, "x": 1.0, "y": 1.0, "w": 0.0, "h": 5.0},
])
def test_malformed_box_rejected(box):
    req, err = scan_tokens_request_from_dict(
        _body(roi_boxes=[box], roi_frame=FRAME))
    assert req is None and err is not None


def test_overshoot_is_clamped_at_boundary():
    box = {"label": "PDP", "score": 0.9, "x": -5.0, "y": 0.0,
           "w": 2000.0, "h": 1300.0}
    req, err = scan_tokens_request_from_dict(
        _body(roi_boxes=[box], roi_frame=FRAME))
    assert err is None
    b = req.roi_boxes[0]
    assert b["x"] == 0.0 and b["w"] == 1600.0 and b["h"] == 1200.0


def test_qa_validator_roi_checks():
    assert not qa.validate_scan_tokens_request(
        _body(roi_boxes=[GOOD_BOX], roi_frame=FRAME))
    assert qa.validate_scan_tokens_request(_body(roi_boxes=[GOOD_BOX]))
    bad = dict(GOOD_BOX)
    bad["label"] = "NOPE"
    assert qa.validate_scan_tokens_request(
        _body(roi_boxes=[bad], roi_frame=FRAME))


def test_recorded_roi_fixture_roundtrip():
    body = json.loads((FIX / "scan_tokens_request_roi.json").read_text())
    req, err = scan_tokens_request_from_dict(body)
    assert err is None and req.roi_boxes
    res = run_scan_tokens(req)
    assert not qa.validate_scan_result(res)
    recorded = json.loads(
        (FIX / "scan_tokens_result_roi.json").read_text())
    assert sorted(res) == sorted(recorded)
