"""Regenerate netra_core/vision_config.json from config.py — run whenever a
shared threshold changes so the Kotlin prepass and Python agree by
construction. CI could diff the committed JSON against this output."""
import json
from pathlib import Path

from netra_core.config import vision_config

out = Path(__file__).resolve().parent.parent / "netra_core" / "vision_config.json"
out.write_text(json.dumps(vision_config(), indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
