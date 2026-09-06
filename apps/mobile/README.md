# NETRA Mobile Diagnostic Harness

A lightweight diagnostic shell for NETRA on Android.

- Built with **Flutter 3.47.2** and **Chaquopy 17.0.0** (Python 3.11 target).
- Connects Flutter to `netra_core` over the `netra.core` MethodChannel via `NetraCorePlugin.kt`.
- UI provides three one-tap probe buttons:
  - `ping`: Verifies channel integrity and reports active engine capabilities.
  - `queue`: Verifies that the on-device SQLite WAL evidence ledger is live.
  - `smoke`: Inspects availability of Python packages (`cv2`, `numpy`, `PIL`, `reportlab`, `statutory_core`, `bridge`).

Full production UI is developed against `docs/BRIDGE_CONTRACT.md`.
