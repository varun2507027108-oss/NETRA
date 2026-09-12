"""test_s2_roi_merge.py — deterministic merge of ML ROI boxes into s2 rois."""

import pytest

from netra_core.context import BBox
from netra_core.stages.s2_roi_merge import merge_roi_boxes, validate_roi_boxes


def _cl(label, x, y, w, h, conf=0.9):
    return {"roi": label, "bbox": BBox(x=x, y=y, w=w, h=h), "conf": conf}


def _ml(label, score, x, y, w, h):
    return {"label": label, "score": score, "x": x, "y": y, "w": w, "h": h}


def test_no_roi_boxes_returns_classical_unchanged():
    cl = [_cl("PACKAGE", 1, 2, 3, 4), _cl("BARCODE", 5, 6, 7, 8)]
    assert merge_roi_boxes(cl, []) == cl
    assert merge_roi_boxes(cl, None) == cl
    assert merge_roi_boxes([], None) == []


def test_ml_authoritative_and_new_labels_added():
    cl = [_cl("PACKAGE", 0, 0, 100, 100), _cl("BARCODE", 5, 5, 10, 10)]
    out = merge_roi_boxes(cl, [
        _ml("PDP", 0.80, 2, 2, 50, 50),
        _ml("PACKAGE", 0.90, 1, 1, 98, 98),
    ])
    assert [r["roi"] for r in out] == ["PACKAGE", "PDP", "BARCODE"]
    assert out[0]["conf"] == 0.90            # ml sorted by score desc
    assert out[0]["bbox"].x == 1             # ML box replaced classical PACKAGE
    assert out[2] is cl[1]                   # classical BARCODE kept as fallback


def test_classical_label_covered_by_ml_is_dropped():
    cl = [_cl("BARCODE", 5, 5, 10, 10)]
    out = merge_roi_boxes(cl, [_ml("BARCODE", 0.7, 6, 6, 9, 9)])
    assert len(out) == 1 and out[0]["conf"] == 0.7


def test_deterministic_order():
    boxes = [_ml("PDP", 0.5, 1, 1, 5, 5), _ml("PRICE", 0.6, 2, 2, 5, 5),
             _ml("PACKAGE", 0.9, 3, 3, 5, 5)]
    a = merge_roi_boxes([], boxes)
    b = merge_roi_boxes([], list(reversed(boxes)))
    assert a == b
    assert [r["roi"] for r in a] == ["PACKAGE", "PRICE", "PDP"]


@pytest.mark.parametrize("bad", [
    {"label": "NOT_REAL", "score": 0.5, "x": 1, "y": 1, "w": 5, "h": 5},
    {"label": "PACKAGE", "score": 1.5, "x": 1, "y": 1, "w": 5, "h": 5},
    {"label": "PACKAGE", "score": 0.5, "x": 1, "y": 1, "w": 0, "h": 5},
    {"label": "PACKAGE", "score": 0.5},
    {"label": "PACKAGE", "score": "abc", "x": 1, "y": 1, "w": 5, "h": 5},
])
def test_malformed_roi_box_raises(bad):
    with pytest.raises(ValueError):
        merge_roi_boxes([], [bad])


# ---- validate_roi_boxes (scan_tokens v1.4.0 wire format) ----------------

def test_validate_absent_and_empty():
    assert validate_roi_boxes(None, 1600, 1200) == []
    assert validate_roi_boxes([], 1600, 1200) == []


def test_validate_passes_clean_box():
    out = validate_roi_boxes([_ml("PDP", 0.9, 10.0, 20.0, 100.0, 50.0)],
                             1600, 1200)
    assert out == [{"label": "PDP", "score": 0.9,
                    "x": 10.0, "y": 20.0, "w": 100.0, "h": 50.0}]


def test_validate_clamps_edge_overshoot():
    out = validate_roi_boxes([_ml("PACKAGE", 0.8, -5.0, 0.0, 100.0, 1605.0)],
                             1600, 1200)
    assert out[0]["x"] == 0.0
    assert out[0]["w"] == 100.0
    assert out[0]["h"] == 1200.0          # clamped to frame height


def test_validate_drops_fully_outside():
    assert validate_roi_boxes([_ml("PRICE", 0.5, 1700.0, 10.0, 50.0, 50.0)],
                              1600, 1200) == []


def test_validate_rejects_bad_frame_dims():
    with pytest.raises(ValueError):
        validate_roi_boxes([_ml("PDP", 0.9, 1.0, 1.0, 5.0, 5.0)], 0, 1200)


@pytest.mark.parametrize("boxes", [
    [{"label": "NOPE", "score": 0.5, "x": 1, "y": 1, "w": 5, "h": 5}],
    [{"label": "PACKAGE", "score": 1.5, "x": 1, "y": 1, "w": 5, "h": 5}],
    [{"label": "PACKAGE", "score": float("nan"), "x": 1, "y": 1, "w": 5, "h": 5}],
    [{"label": "PACKAGE", "score": 0.5, "x": 1, "y": 1, "w": 0, "h": 5}],
    [{"label": "PACKAGE", "score": 0.5, "x": float("inf"), "y": 1, "w": 5, "h": 5}],
    ["PACKAGE"],
    [_ml("PACKAGE", 0.5, 1, 1, 5, 5)] * 65,          # count cap
])
def test_validate_structural_errors(boxes):
    with pytest.raises(ValueError):
        validate_roi_boxes(boxes, 1600, 1200)
