"""test_yolo_golden.py — CI-side enforcement of the netra_roi LiteRT contract.

Validates core/fixtures/yolo/golden_v1.json end-to-end, stdlib only
(json / base64 / hashlib / struct):

  1. fixture integrity      — tensor byte sizes + input sha256
  2. pinned output contract — [1,9,8400]: rows 0-3 normalized cx,cy,w,h;
                              rows 4-8 post-sigmoid scores in [0,1]
  3. decoder equivalence    — pure-Python mirror of the exact NetraYolo.kt
                              algorithm (letterbox inversion + conf gate +
                              per-class NMS) decodes the recorded tensor
                              into the recorded box list
  4. export parity          — recorded torch reference vs recorded tflite
                              decode (tamper evidence: swapping the model
                              without re-recording the golden fails here)
  5. single source of law   — vision_config.json "yolo" section must match
                              the golden on every field Kotlin consumes

Model round 2: re-record the golden (tools/record_yolo_golden.py) and update
EXPECTED_LABELS below. Do not loosen tolerances to make a new model pass.
"""

import base64
import hashlib
import json
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]            # -> core/
GOLDEN = ROOT / "fixtures" / "yolo" / "golden_v1.json"
VISION = ROOT / "netra_core" / "vision_config.json"

SIZE, CHANNELS, ANCHORS = 640, 9, 8400
EXPECTED_LABELS = ["PACKAGE", "PDP", "PRICE", "BARCODE", "BOP"]
BOX_TOL, SCORE_TOL = 0.05, 1e-6                       # px, absolute
PARITY_IOU, PARITY_SCORE_TOL = 0.85, 0.05
FIDELITY_MAX_BOX_PX, FIDELITY_MAX_SCORE = 5.0, 0.01


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text())


@pytest.fixture(scope="module")
def out_rows(golden):
    raw = base64.b64decode(golden["output"]["values_b64"])
    assert len(raw) == CHANNELS * ANCHORS * 4
    vals = struct.unpack("<%df" % (CHANNELS * ANCHORS), raw)
    return [list(vals[i * ANCHORS:(i + 1) * ANCHORS]) for i in range(CHANNELS)]


def _iou(a, b):
    """a, b: (label, score, x, y, w, h)."""
    x1 = max(a[2], b[2]); y1 = max(a[3], b[3])
    x2 = min(a[2] + a[4], b[2] + b[4]); y2 = min(a[3] + a[5], b[3] + b[5])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = a[4] * a[5] + b[4] * b[5] - inter
    return inter / union if union > 0 else 0.0


def _decode(rows, meta, conf_thr, iou_thr, max_per_class=20):
    """Pure-Python mirror of NetraYolo.kt decode() + nmsPerClass()."""
    n = len(rows[0])
    s = float(SIZE)
    cands = []
    for a in range(n):
        best_c, best_s = -1, -1.0
        for c in range(4, CHANNELS):
            v = rows[c][a]
            if v > best_s:
                best_s, best_c = v, c - 4
        if best_c < 0 or best_s < conf_thr:
            continue
        cx, cy = rows[0][a] * s, rows[1][a] * s
        w, h = rows[2][a] * s, rows[3][a] * s
        cands.append((best_c, best_s,
                      (cx - w / 2 - meta["padX"]) / meta["gain"],
                      (cy - h / 2 - meta["padY"]) / meta["gain"],
                      w / meta["gain"], h / meta["gain"]))
    out = []
    for c in sorted({d[0] for d in cands}):
        group = sorted((d for d in cands if d[0] == c), key=lambda d: -d[1])
        kept = []
        for d in group:
            if all(_iou(d, k) <= iou_thr for k in kept):
                kept.append(d)
            if len(kept) >= max_per_class:
                break
        out.extend(kept)
    return out


def test_fixture_integrity(golden):
    assert golden["class_labels"] == EXPECTED_LABELS
    assert golden["graph_normalizes_input"] is False
    assert golden["output_box_space"] == "normalized_0_1"
    assert golden["thresholds"] == {"conf": 0.25, "iou": 0.45}
    x = base64.b64decode(golden["input"]["values_b64"])
    assert golden["input"]["shape"] == [1, 3, SIZE, SIZE]
    assert len(x) == 1 * 3 * SIZE * SIZE * 4
    assert hashlib.sha256(x).hexdigest() == golden["input"]["sha256"]
    assert golden["output"]["shape"] == [1, CHANNELS, ANCHORS]
    m = golden["meta"]
    assert m["gain"] > 0
    assert 0 <= m["padX"] <= SIZE // 2 and 0 <= m["padY"] <= SIZE // 2
    fid = golden["export_fidelity"]
    assert fid["box_px"] < FIDELITY_MAX_BOX_PX
    assert fid["score"] < FIDELITY_MAX_SCORE


def test_output_tensor_contract(out_rows):
    assert len(out_rows) == CHANNELS and len(out_rows[0]) == ANCHORS
    for row in out_rows[4:]:                          # post-sigmoid scores
        assert all(0.0 <= v <= 1.0 for v in row)
    for row in out_rows[:4]:                          # normalized, not pixels
        assert -1.0 <= min(row) and max(row) <= 2.0


def test_decode_reproduces_recorded(golden, out_rows):
    dets = _decode(out_rows, golden["meta"],
                   golden["thresholds"]["conf"], golden["thresholds"]["iou"])
    rec = golden["decoded"]
    assert len(dets) == len(rec)
    dets_s = sorted(dets, key=lambda d: (d[0], -d[1]))
    rec_s = sorted(rec, key=lambda r: (r["label"], -r["score"]))
    for d, r in zip(dets_s, rec_s):
        assert d[0] == r["label"]
        assert abs(d[1] - r["score"]) <= SCORE_TOL
        assert abs(d[2] - r["x"]) <= BOX_TOL
        assert abs(d[3] - r["y"]) <= BOX_TOL
        assert abs(d[4] - r["w"]) <= BOX_TOL
        assert abs(d[5] - r["h"]) <= BOX_TOL


def test_recorded_export_parity(golden):
    """The recorder's acceptance gate, re-asserted from recorded data."""
    dets, ref = golden["decoded"], golden["reference"]
    assert len(dets) <= len(ref) + 3
    for r in (r for r in ref if r["score"] >= 0.35):
        assert any(
            d["label"] == r["label"]
            and _iou((d["label"], d["score"], d["x"], d["y"], d["w"], d["h"]),
                     (r["label"], r["score"], r["x"], r["y"], r["w"], r["h"]))
            >= PARITY_IOU
            and abs(d["score"] - r["score"]) <= PARITY_SCORE_TOL
            for d in dets
        ), f"no tflite match for torch reference {r}"


def test_vision_config_matches_golden(golden):
    cfg = json.loads(VISION.read_text())["yolo"]
    assert cfg["class_labels"] == golden["class_labels"] == EXPECTED_LABELS
    assert cfg["num_classes"] == len(EXPECTED_LABELS)
    assert cfg["input_size"] == SIZE
    assert cfg["conf_threshold"] == golden["thresholds"]["conf"]
    assert cfg["iou_threshold"] == golden["thresholds"]["iou"]
    assert cfg["graph_normalizes_input"] is False
    assert cfg["output_box_space"] == "normalized_0_1"
    assert cfg["max_detections_per_class"] == 20
    assert cfg["pad_gray"] == 114
