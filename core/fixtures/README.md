# NETRA fixtures — real-world validation set

## Photograph protocol (per package)
- print the fiducial card (`scripts/make_fiducial_card.py`) at 100% scale
- FRONT (declaration side) photo: card held flat on the SAME face, near
  text but not covering it; 25–35 cm; label fills the frame; daylight
  shade; no flash; hold steady
- optional BACK photo (consumer care block)
- measure with a ruler: height+width (flat) or height+diameter
  (cylinder) in cm — these become golden PDA values

## Ground truth — `labels_gt.json` (copy the template)
one entry per image key; `fields` = EXACTLY what is printed (we test the
pipeline, not our memory); `expect_fail` = rule keys ([] = compliant);
omit fields you cannot read reliably.

## Run
    .venv\Scripts\python scripts\make_fixtures.py
    .venv\Scripts\python scripts\make_fixtures.py --report-only --psm 6

RETRY rows are capture problems (re-photograph). Mismatch rows split
into miss: (pipeline missed a violation) and extra: (found more than GT
says) — open golden_report.json to decide GT gap vs OCR gap vs logic bug.
Keep committed photos ~1600 px / <2 MB.
