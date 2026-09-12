#!/usr/bin/env python3
"""Regenerate netra_core/vision_config.json from config.py and golden_v1.json.

Run whenever a shared threshold changes so the Kotlin prepass and Python
agree by construction.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from netra_core.config import vision_config

payload = vision_config()

# add to the payload construction in tools/export_vision_config:
golden = json.loads((ROOT / "core/fixtures/yolo/golden_v1.json").read_text())
payload["yolo"] = {
    "input_size": 640,
    "num_classes": len(golden["class_labels"]),
    "class_labels": golden["class_labels"],
    "conf_threshold": golden["thresholds"]["conf"],
    "iou_threshold": golden["thresholds"]["iou"],
    "max_detections_per_class": 20,
    "graph_normalizes_input": golden["graph_normalizes_input"],   # false
    "output_box_space": golden.get("output_box_space", "normalized_0_1"),
    "pad_gray": 114,
}

out = ROOT / "core" / "netra_core" / "vision_config.json"
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
