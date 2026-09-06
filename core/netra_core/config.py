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

# ---- Stage 3: metric calibration ------------------------------------------
ARUCO_MARKER_MM = 40.0           # marker side on the printed fiducial card
FOCAL_RATIO_DEFAULT = 1.2        # assumed f = ratio x max(w,h) w/o intrinsics
CYL_THETA_LIMIT_DEG = 80.0       # flatten arc up to this angle from the front
CYL_MIN_RADIUS_PX = 40.0         # smaller "cylinder" = estimation noise
CYL_MAX_RADIUS_MM = 250.0        # sanity bound on recovered radius
PDA_SANITY_CM2 = (1.0, 25000.0)  # PDA outside this range -> not computed
MAX_RECT_SCALE = 8.0             # rectified extent cap (oblique-marker guard)

# ---- Stage 2: package geometry (deterministic engine) --------------------
PKG_MIN_AREA_FRAC = 0.15         # silhouette smaller -> not a package
PKG_MAX_AREA_FRAC = 0.90         # silhouette covering ~the frame -> background
PKG_BORDER_TOUCH_MAX = 2         # contour bbox sides allowed to touch frame edge
PKG_CROP_MARGIN_FRAC = 0.10      # margin around package(+fiducial) union
PKG_CROP_MAX_AREA_FRAC = 0.85    # crop larger than this -> not worth cropping
SHAPE_SAGITTA_FRAC = 0.04        # top-edge sagitta/width -> cylindrical
BARCODE_MIN_ASPECT = 1.4         # w/h of a 1D barcode region
BARCODE_MIN_EDGE_DENSITY = 0.28  # in-box vertical-edge density
BARCODE_MIN_COL_CV = 1.0         # column-profile variation (stripe periodicity)


# ---- vision prepass shared config (Kotlin reads this JSON; one source) ----
def vision_config() -> dict:
    """Statutory thresholds + calibration constants shared with the Kotlin
    prepass. ONE source of truth: config.py values serialize to the JSON
    bundled in the wheel; NetraVision.kt reads the JSON, never hardcodes."""
    cfg = {k: globals()[k] for k in (
        "LAPLACIAN_VAR_MIN", "GLARE_PIXEL_MAX", "GLARE_AREA_PCT_MAX",
        "ARUCO_MARKER_MM")}
    cfg.update({
        "ARUCO_DICT": "DICT_4X4_50",
        "SOLVEPNP_SCALE_TOLERANCE": 0.15,
        "MAX_TILT_DEG": 25.0,
        "PDA_CYL_COEF": 0.40,
        "PDA_SANITY_CM2": list(PDA_SANITY_CM2),
    })
    return cfg