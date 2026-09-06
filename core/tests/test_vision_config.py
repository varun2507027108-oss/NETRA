import json
from pathlib import Path

from netra_core.config import vision_config

JSON_PATH = Path(__file__).resolve().parent.parent / "netra_core" / \
    "vision_config.json"


def test_vision_config_matches_committed_json():
    """The Kotlin prepass reads the committed JSON; config.py is the law.
    Drift between them is a build error — regenerate with
    scripts/export_vision_config.py."""
    committed = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert committed == vision_config()


def test_statutory_values_present():
    cfg = vision_config()
    assert cfg["LAPLACIAN_VAR_MIN"] == 100.0
    assert cfg["GLARE_PIXEL_MAX"] == 242
    assert cfg["PDA_CYL_COEF"] == 0.40
    assert cfg["PDA_SANITY_CM2"] == [1.0, 25000.0]
