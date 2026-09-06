# NETRA Android integration — the native seam

Kotlin side of the bridge: `native/android/NetraCorePlugin.kt` (the
MethodChannel pipe), `native/android/NetraKeystore.kt` (KeyStore ECDSA
P-256 signing of the pinned payload), `native/android/netra_smoke.py`
(the environment spike). Flutter/Dart lives in `apps/mobile` (Antigravity,
built against `BRIDGE_CONTRACT.md`); these three files are the platform
half that the Flutter agent must not invent.

## What is certain vs the one open risk

Certain in every architecture path: the statutory engine (s5/s6), the
evidence ledger, and sync run in Python via Chaquopy — one codebase for
the law on desktop AND device; signing stays in Android KeyStore; the
bridge payloads are contract JSON, unchanged.

Open risk (resolved by the spike below, not by assertion): whether
`cv2` / `pillow` / `reportlab` install and import under Chaquopy for
your target ABI. Do not guess — measure.

## File placement (after `flutter create apps/mobile`)

| File | Destination |
|---|---|
| `NetraCorePlugin.kt`, `NetraKeystore.kt` | `apps/mobile/android/app/src/main/java/netra/core/` (adjust package to taste; keep both files in one package) |
| `netra_smoke.py` | `apps/mobile/android/app/src/main/python/` (Chaquopy's default python source set) |

`MainActivity` wiring:

```kotlin
class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        NetraCorePlugin.register(this, flutterEngine.dartExecutor.binaryMessenger)
    }
}
```

`minSdk 24` (covers KeyStore-EC (23) and current Chaquopy).

## Gradle / Chaquopy (verify shapes against the Chaquopy docs version
## you pin — the DSL moved between 14.x and 15.x)

```groovy
// app/build.gradle  (groovy shown; kts analogous)
plugins {
    id "com.chaquo.python"   // + version, resolved from the chaquo maven repo
}
android { defaultConfig { minSdk 24 } }
chaquopy {
    defaultConfig {
        version = "3.11"          // check supported versions for your plugin
        pip {
            // built once from core/ (see below); local file paths are
            // supported in the install list — check current docs
            install "netra_core-0.1.0-py3-none-any.whl"
            install "numpy"
            // THE SPIKE decides these three lines:
            install "opencv-python"
            install "pillow"
            install "reportlab"
        }
    }
}
```

Build the core wheel:

    cd core
    .venv\Scripts\python -m pip wheel . --no-deps -w ..\native\android\wheels

then copy the wheel next to `build.gradle` (or reference the path).

## Step 0 — the spike (15 minutes, do this BEFORE anything else)

Debug-build the app with `netra_smoke.py` in place; call it once (a
hidden "environment check" button is fine); read the JSON:

| Outcome | Path | Meaning |
|---|---|---|
| cv2 ok, reportlab ok | **A** | Full Python core on device. Ship as-is. |
| cv2 FAIL, reportlab ok | **B1** | Vision (s1–s3) moves to Kotlin + the official OpenCV Android SDK (the spec's own "Dart FFI / native C++" flavor); Python keeps s5/s6/s7/s8. Needs a small bridge extension — plan a session for it. |
| cv2 ok, reportlab FAIL | **B2** | Dossier PDF renders in Kotlin (`android.graphics.pdf`); Python computes checks + hashes. s7 splits. |
| both FAIL | **B3** | Python = the law + ledger + sync (s5/s6/s8); tokens injected from Kotlin-side ML Kit; s1–s3 and s7 in Kotlin. |

In every path `statutory_core` and `bridge` must report `ok` — those are
stdlib by design (the day-one architecture rule pays off here).

## Signing flow, end to end (Kotlin side)

```kotlin
// after a scan completes with result.dossier != null:
val attachJson = NetraKeystore.attachRequestFor(scanResultJson)
val resp = /* invoke MethodChannel("netra.core") "attach_signature" with attachJson */
// resp: {accepted, sig_status, verified, error?} per contract §8
```

## What is NEVER in Kotlin

Statutory logic. Verdicts, rule checks, USP math, Table-I bands — all
live in `netra_core.rules` and only there. Kotlin pipes JSON and signs
the exact payload string. If a Kotlin file ever grows a rule citation,
the architecture is broken.

## Spike results — recorded on-device (arm64-v8a, Chaquopy 17.0.0, Python 3.11)

Baseline build: dependency-free wheel only — no pip tiers (deliberate:
minimum failure surface; `ping` works regardless of vision-stack outcome).

| Probe | Result |
|---|---|
| ping | s4/s5/s6 live, `sync: true`; s1/s2/s3/s7 excluded (cv2/reportlab not installed) |
| queue_status | SQLite WAL evidence ledger operational on internal storage |
| smoke | `statutory_core: ok` · `bridge: ok` · cv2/numpy/PIL/reportlab not installed |

**Verdict: the seam holds on real hardware.** `run_scan` on this baseline
returns an INTERNAL envelope (pipeline imports cv2 at module top) —
expected; capabilities are probed before the vision decision. Phase 2
(tiered pip installs) decides Path A-lean vs B1 — see the decision tree.

### Phase 2 results — Tiered Pip Probes (arm64-v8a, Chaquopy 17.0.0)

| Tier | Package | Result | Notes |
|---|---|---|---|
| Tier 1 | `numpy` | **PASS** | Chaquopy prebuilt `numpy-1.26.2` + `chaquopy-openblas` installed. `smoke` reported `"numpy": "ok"`. |
| Tier 2 | `reportlab` (+ `pillow`) | **PASS** | `reportlab-5.0.1` + prebuilt `pillow-11.0.0` installed. `smoke` reported `"reportlab": "ok"`, `"PIL": "ok"`. `ping` lit up `"s7_dossier"` (`"dossier": true`). |
| Tier 3 | `opencv-python` | **FAIL** | `No matching distribution found for opencv-python`. No Android wheels exist on PyPI or Chaquopy index. |

**Verdict: Confirmed Path B1.**
- `s7_dossier` is live on-device (text & layout PDF dossier generation operational with reportlab + pillow).
- Python owns the law + dossier + verification: `s4` (token ingestion), `s5`, `s6`, `s7`.
- Kotlin/Native owns pixels: camera, ML Kit (line tokens), and OpenCV Android SDK for `s1/s2/s3`.

## Phase 3 — the B1 scan path (live)

`scan_tokens` (contract v1.3) is implemented and tested: the platform
sends ML Kit line tokens (+ optional quality/geometry/glyphs/image) and
receives the standard ScanResult with on-device dossier + ledger. A
Dart-only app (google_mlkit_text_recognition) can drive the full loop
today; the Kotlin vision pre-pass (s1 Laplacian/glare, s3 ArUco +
solvePnP via `org.opencv:opencv` on Maven Central — ArUco is in the
main objdetect module since 4.7) is the enhancement that fills
`quality` / `geometry`, and slots into the same request with no
further contract changes.

### Phase 3 hardware proof — scan_tokens loop on-device

Purple-button diagnostic: tokens + geometry + quality -> MethodChannel ->
scan_tokens -> **verdict VIOLATION (7 FAIL / 4 PASS), on-device dossier
generated (sha256 recorded, app-internal storage), ledger row filed
(total: 1, dossiers: 1, pending_sync: 1)**. Screenshot archived with the
spike results. The B1 loop is closed on real hardware — remaining
device work is OCR + camera wiring (Antigravity) and the Kotlin vision
pre-pass.

## Phase 4 — the Kotlin vision pre-pass A/B proof (live on hardware)

Native OpenCV vision pre-pass (`s1_frame_quality` + `s3_calibration`)
implemented in `NetraVision.kt` (`org.opencv:opencv:4.9.0`), exposed over
`vision_prepass` MethodChannel. Evaluated on real ARM hardware against the
desktop Python reference (`core/scripts/ab_prepass.py`) using identical bytes
from `core/fixtures/synth/labels/S01_clean.jpg` (200 px / 40 mm marker).

### Comparison: Desktop Python Reference vs Real Android Device

| Metric | Desktop Python Reference (`ab_prepass.py`) | Device Kotlin Pre-pass (`NetraVision.kt`) | Residual / Delta |
|---|---|---|---|
| `marker_detected` | `true` | `true` | **Match** |
| `marker_id` | `0` | `0` | **Match** |
| `mm_per_px` | `0.201005` | `0.201005` | **0.000% (Identical to 6 decimal places)** |
| `tilt_deg` | `0.0` | `0` | **Match** |
| `quality.ok` | `true` | `true` | **Match** |
| `laplacian_var` | `793.2898908602531` | `793.2898908602531` | **0.000% (Bit-exact)** |
| `glare_pct` | `0.4268269230769231` | `0.4268269230769231` | **0.000% (Bit-exact)** |
| `quality.prompts` | `[]` | `[]` | **Match** |
| `geometry.warnings` | `[]` | `[]` | **Match** |

### Output JSON on-device:
```json
{
  "quality": {
    "ok": true,
    "laplacian_var": 793.2898908602531,
    "glare_pct": 0.4268269230769231,
    "prompts": []
  },
  "geometry": {
    "marker_detected": true,
    "mm_per_px": 0.201005,
    "marker_id": 0,
    "tilt_deg": 0,
    "warnings": []
  }
}
```

**Verdict: The A/B comparison passes with 0.000% residual.**
The phone runs s1 + s3 natively in Kotlin with OpenCV 4.9, producing bit-exact
quality numbers and planar scale to Python reference on identical bytes.




