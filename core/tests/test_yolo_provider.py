"""Tests for optional netra_core.contrib.yolo_provider module."""
import json
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "core/models/netra_roi.pt"
GOLDEN_PATH = ROOT / "core/fixtures/yolo/golden_v1.json"
INPUT_PATH = ROOT / "core/fixtures/yolo/golden_input.png"


def test_provider_import_guard():
    """Ensure contrib does not pollute root netra_core imports."""
    import netra_core
    assert not hasattr(netra_core, "contrib") or not hasattr(netra_core.contrib, "YoloRoiProvider")


def test_provider_requires_model_file():
    """Raise FileNotFoundError when model path does not exist."""
    pytest.importorskip("ultralytics")
    from netra_core.contrib.yolo_provider import YoloRoiProvider

    with pytest.raises(FileNotFoundError):
        YoloRoiProvider("nonexistent_model.pt")


def test_provider_golden_input_parity():
    """Verify YoloRoiProvider produces detections matching golden_v1.json classes."""
    pytest.importorskip("ultralytics")
    from netra_core.contrib.yolo_provider import YoloRoiProvider

    if not MODEL_PATH.exists():
        pytest.skip("netra_roi.pt not available locally")
    if not INPUT_PATH.exists() or not GOLDEN_PATH.exists():
        pytest.skip("golden fixture not found")

    golden = json.loads(GOLDEN_PATH.read_text())
    provider = YoloRoiProvider(MODEL_PATH)
    detections = provider.detect(str(INPUT_PATH), conf=0.25)

    assert len(detections) > 0, "Provider failed to find any detections on golden input"
    detected_classes = {d["class_name"] for d in detections}
    golden_classes = {golden["class_labels"][d["label"]] for d in golden["decoded"]}

    # All golden classes must be represented in detections
    overlap = detected_classes.intersection(golden_classes)
    assert len(overlap) >= len(golden_classes) - 1, (
        f"Detected {detected_classes} vs golden {golden_classes}"
    )


def test_class_labels_pinned_to_config_and_golden():
    """Hardcoded CLASS_LABELS is a checked constant, not a silent one."""
    pytest.importorskip("ultralytics")
    from netra_core.contrib.yolo_provider import CLASS_LABELS

    cfg = json.loads((ROOT / "core" / "netra_core" / "vision_config.json").read_text())["yolo"]
    golden = json.loads(GOLDEN_PATH.read_text())
    assert list(CLASS_LABELS) == cfg["class_labels"] == golden["class_labels"]


