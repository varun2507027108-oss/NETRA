"""NETRA — central tuning constants.

Everything an SIH evaluator might probe lives here; stages must read
thresholds from this module instead of hard-coding numbers.
"""

# ---- Stage 1: frame quality gate ---------------------------------------
LAPLACIAN_VAR_MIN = 100.0   # below this -> motion blur -> RETRY
GLARE_PIXEL_MAX = 242       # luminance >= this -> specular glare candidate
GLARE_AREA_PCT_MAX = 1.0    # % of frame area allowed before RETRY

# ---- Stage 6: statutory tolerances --------------------------------------
USP_TOLERANCE = "0.01"      # rupees (1 paisa); str so Decimal() stays exact
FONT_TOL_MM = 0.1           # measurement slack vs Table-I minimums
PIN_CODE_LEN = 6            # Rule 6(1)(a)

# ---- Stage budgets (ms); see scripts/bench_pipeline.py ------------------
STAGE_BUDGET_MS = {
    "s1_frame_quality": 3.0,
    "s2_geometry_detect": 39.0,
    "s3_calibration": 15.0,
    "s4_ocr": 1200.0,       # dominant cost; tiers run per ROI
    "s5_field_extract": 1.0,
    "s6_metrology": 1.0,
    "s7_dossier": 20.0,
    # s8_sync is async — never on the critical path
}