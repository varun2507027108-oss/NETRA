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
