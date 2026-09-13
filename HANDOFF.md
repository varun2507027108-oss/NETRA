# NETRA Project Handoff — SIH26026 (rev 2, post model-round-1 landing)
Repo: github.com/varun2507027108-oss/NETRA · status: ~95% · last verified commit cc5b70e

## Architecture (unchanged, hardware-proven)
One stdlib-only Python engine (netra_core) in pytest / FastAPI bridge /
Chaquopy. Kotlin = pipe + signer + vision prepass + [NEW] on-device YOLO.
Dart renders. Zero statutory logic outside Python.

## Completed since rev 1
- netra_roi r1: trained, landed, hash-pinned; LiteRT export contract
  empirically pinned (golden_v1.json): input [1,3,640,640] NCHW /255;
  output [1,9,8400] normalized boxes + sigmoid scores; Kotlin owns NMS.
- Four-runtime parity: torch / desktop tflite / Python mirror / LiteRT
  on-device — 1.6e-6 max diff.
- scan_tokens v1.4.0: roi_boxes + roi_frame (optional, backward compat),
  schema validation, pipeline merge (ML-authoritative, classical fallback),
  2 new fixtures. All 13 fixtures valid.
- Android: NetraYolo.kt decoder, prepass YOLO stage, Dart forwarding,
  model packaged in src/main/assets, LiteRT 1.0.1 pin, device golden
  test 4/4, fallback logging.
- CI: Python (3.11/3.13) + android-compile (compileDebugKotlin, gradle
  wrapper tracked, NETRA_BUILD_PYTHON seam, local.properties generated).
- Fixed en route: mm_per_px/marker_detected wrong-level reads (calibration
  never reached engine from app), model never packaged into APK.

## Remaining
1. 3 real photos -> make_fixtures -> golden_report.json -> RESULTS_R1.pdf
   (THE missing real-world number) [Harness state: `core/scripts/make_fixtures.py` and `tools/make_results_pdf.py` ready; waiting for 3 camera captures in `Downloads/netra_photos/`]
2. s5 PDP-bias spec + patch (last phantom)
3. Step 3 screens (dossier viewer, history, sync)
4. UX round (auto-capture, plain language), design-law fixes [see audit]
5. Doc polish, Phase E rehearsal
Backlog: assembleDebug CI gate; int8 model path; Dart CI job.

## Key commands
- `doctor`: `python core/scripts/doctor.py`
- `reset_demo_state`: `python core/scripts/reset_demo_state.py`
- `bench_pipeline`: `python core/scripts/bench_pipeline.py`
- `record_contract_fixtures`: `python core/scripts/record_contract_fixtures.py`
- `refresh_wheel`: `python tools/refresh_wheel.py` (mandatory on any `netra_core` change before rebuilding APK)
- `export_vision_config`: `python tools/export_vision_config.py` (or `python core/scripts/export_vision_config.py`)
- `record_yolo_golden`: `python tools/record_yolo_golden.py`
- `make_results_pdf`: `python tools/make_results_pdf.py`
