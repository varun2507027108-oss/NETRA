# NETRA — the 5-minute judge demo

Run order (rehearse twice, verbatim):

| Time | Beat | What you do | What you say |
|---|---|---|---|
| 0:00 | The problem | one slide | "Tens of millions of SKUs, under 0.01% inspected, and the violations are invisible — a 1.2 mm font, a missing 'incl. of all taxes', math that doesn't divide." |
| 0:30 | The scan | `python scripts\demo_all.py` | "One photograph. Five planted statutory traps. Watch the verdict table." — read the FAIL rows aloud, one law each |
| 1:15 | The dossier | open the PDF | "Every finding carries its rule citation and its evidence box. Last page: the certificate under section 63(4) of the Bharatiya Sakshya Adhiniyam — the successor to 65B, cited correctly." |
| 2:00 | The signature | point at the console | "ECDSA P-256 from the Android KeyStore — the key never leaves secure hardware. On desktop we prove the chain with a dev key." |
| 2:30 | Offline-first | THE LIVE MOMENT (below) | "Scans complete with zero connectivity. Evidence queues. Sync is idempotent and nothing is ever deleted." |
| 3:15 | The institution | console phases 5-7 | "The gateway maps violation density — PostGIS heatmaps for inspector route planning — and emits e-Daakhil and NCH 1915 payloads." |
| 3:45 | The architecture | one slide | "Eight stages, all live. The legal decision path is deterministic: 0.45 ms, ~320 tests pinned at statutory boundaries. The bridge contract is machine-validated law, not documentation." |
| 4:15 | Honest scope | one slide | "Live today: the full deterministic chain, end to end. In progress: on-device ML Kit, YOLO ROIs, and the field fixture set — the machinery to measure real-world precision is already in the repo." |

## The live offline moment (do this, don't narrate it)

1. Turn WiFi off.
2. Run a scan (demo or, when the app exists, the device).
3. Show it completes — verdict, dossier, ledger row. Nothing blocks.
4. Show the queue: pending, attempts tracked.
5. Turn WiFi on. Sync drains. Show the gateway stats update.

Thirty seconds, and the offline-first claim stops being a slide.

## Contingency insurance

| If... | Then... |
|---|---|
| tesseract missing on the demo machine | demo_all.py doesn't need it (dev-injection path) — say so, it's a feature |
| Flutter app not ready | demo via `demo_all.py` + the desktop bridge; the contract fixtures prove the app's payloads are already law |
| PDF viewer/projector fails | the console output IS the demo; SUBMISSION.md carries the narrative |
| a judge asks about accuracy | JUDGE_QA.md Q1 — never improvise this answer |
| demo machine dies | repo is public; CI badge proves the suite runs anywhere; clone-and-run is in SUBMISSION.md |
