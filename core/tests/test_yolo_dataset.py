"""Validate the synthetic YOLO corpus: label legality, class presence,
and byte-exact determinism (the property that lets Colab regenerate the
IDENTICAL dataset without uploading it)."""
import random
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("cv2")

import importlib.util

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / \
    "make_yolo_dataset.py"
_spec = importlib.util.spec_from_file_location("mkyd", _SCRIPT)
mky = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mky)


def _labels(out, split, stem):
    p = out / "labels" / split / f"{stem}.txt"
    rows = [line.split() for line in p.read_text().splitlines()]
    return [(int(r[0]), [float(v) for v in r[1:]]) for r in rows]


def test_labels_are_legal_and_complete(tmp_path):
    stats = mky.generate(tmp_path, n=8, val=2, seed=20260906)
    assert stats["train"] == 6 and stats["val"] == 2
    assert stats["by_class"]["PACKAGE"] == 8
    assert stats["by_class"]["PDP"] == 4          # even i -> front
    assert stats["by_class"]["BOP"] == 4          # odd i -> back
    for split in ("train", "val"):
        for lbl in (tmp_path / "labels" / split).glob("*.txt"):
            for row in (line.split() for line in lbl.read_text().splitlines()):
                assert len(row) == 5
                cid = int(row[0])
                assert 0 <= cid < len(mky.CLASSES)
                cx, cy, w, h = (float(v) for v in row[1:])
                assert all(0.0 <= v <= 1.0 for v in (cx, cy, w, h))


def test_barcodes_present_when_seeded(tmp_path):
    stats = mky.generate(tmp_path, n=40, val=4, seed=20260906)
    assert stats["by_class"]["BARCODE"] > 0


def test_deterministic_bytes(tmp_path):
    mky.generate(tmp_path / "a", n=4, val=0, seed=7)
    mky.generate(tmp_path / "b", n=4, val=0, seed=7)
    fa = sorted((tmp_path / "a" / "images" / "train").glob("*.jpg"))
    fb = sorted((tmp_path / "b" / "images" / "train").glob("*.jpg"))
    assert [f.name for f in fa] == [f.name for f in fb]
    assert all(x.read_bytes() == y.read_bytes() for x, y in zip(fa, fb))
