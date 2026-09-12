"""Regenerate netra_core/vision_config.json from config.py — run whenever a
shared threshold changes so the Kotlin prepass and Python agree by
construction. CI could diff the committed JSON against this output."""
import json
from pathlib import Path

from netra_core.config import vision_config

ROOT = Path(__file__).resolve().parent.parent.parent
payload = vision_config()

golden_path = ROOT / "core" / "fixtures" / "yolo" / "golden_v1.json"
if golden_path.exists():
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
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

out = Path(__file__).resolve().parent.parent / "netra_core" / "vision_config.json"
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")

