# NETRA — SIH26034 submission brief

**Offline-first, deterministic statutory compliance auditing for packaged
commodities** — Legal Metrology (Packaged Commodities) Rules, 2011.

## The problem, restated

Rule 6 and Rule 7 of the LMPC Rules demand a dozen machine-checkable
declarations on every package: 6-digit PINs, "incl. of all taxes",
₹-per-unit arithmetic, SI unit syntax, and font heights that scale with the
Principal Display Area. Inspectors cover < 0.01% of circulating packages,
and the violations are sub-visual — a 1.2 mm numeral is invisible at
counter speed but is a statutory violation.

## What NETRA does

One photograph → deterministic audit → signed, court-shaped dossier →
offline queue → institutional gateway → e-Daakhil / NCH 1915 payloads.
All 8 spec stages are live on a deterministic engine (no model in the legal
decision path); the device round swaps in ML Kit and YOLO26n without
changing the architecture or the bridge contract.

## Four differentiators

**1. A deterministic statutory engine.** Rule 6/7/13/26 encoded as pure
stdlib logic with `Decimal` arithmetic: 0.45 ms per scan, ~290 unit tests
pinned at statutory boundaries (PDA bands 50/100/500/2500 cm², the ₹0.01
USP tolerance, the exactly-one-unit exemption, tobacco/cement carve-outs,
the "Made in PRC" ambiguity trap). Every finding carries its rule citation
and evidence bbox. Same input, same verdict, every time — auditable, not
probabilistic.

**2. A court-admissible evidence chain.** SHA-256(image) → dossier PDF →
SHA-256 → hardware-backed ECDSA P-256 (Android KeyStore / iOS Secure
Enclave) over a pinned payload; the PDF embeds a certificate template under
§63(4) of the Bharatiya Sakshya Adhiniyam, 2023 — the successor to §65B(4)
IEA, cited correctly. The ledger is append-only SQLite (WAL); sync is
idempotent and never deletes evidence.

**3. Offline-first field reality.** A scan in a zero-barrier kirana basement
behaves identically to one on 5G: the network only ever touches the queue
drain. Sync semantics are graded (synced / failed / pending), so a rejected
envelope surfaces for a human instead of vanishing.

**4. Institutional integration.** Standardized e-Daakhil and NCH 1915
payload builders (respondent extraction from OCR addresses, PIN-zone
routing), a PostgreSQL/PostGIS gateway with violation heatmaps — directly
serving the spec's goal of mapping regional violation density for inspector
route planning.

## Verify it in ten minutes

```bash
git clone https://github.com/varun2507027108-oss/NETRA && cd NETRA/core
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pip install -e ..\backend
.venv\Scripts\pytest                              # ~290 tests, statutory boundaries
.venv\Scripts\python scripts\demo_dossier.py      # VIOLATION verdict → PDF (open it:
                                                  #   evidence boxes, citations, §63(4))
                                                  # → ECDSA signature verified → ledger
.venv\Scripts\python scripts\demo_sync.py         # ledger → gateway → heatmap →
                                                  #   e-Daakhil + NCH payloads
.venv\Scripts\python scripts\bench_pipeline.py    # per-stage latency vs spec budgets
```

## Spec checklist → NETRA checks

| Spec §4 checklist item | NETRA rules evaluated |
|---|---|
| 1. PDA & font height | Rule 7 (Table-I bands), Rule 7(3) glyph aspect, Rule 7(4) PDA |
| 2. Identity & origin | Rule 6(1)(a) (+PIN), 6(1)(aa), 6(1)(b) |
| 3. Net quantity & units | Rule 6(1)(c) + Rule 13 prohibited syntax |
| 4. Pricing & USP | Rule 6(1)(e) phrase, Rule 6(11) math (₹0.01 tolerance) |
| 5. Date & redressal | Rule 6(1)(d), Rule 6(1)(n) |
| 6. Evidence dossier | s7 PDF + hash chain + platform signature + §63(4) |

## Honest scope

Live today: the full deterministic chain — quality gate, calibration,
extraction, statutory engine, dossier, ledger, sync, gateway, exports —
running end-to-end on desktop (Tesseract dev OCR tier) and on synthetic
photographs with a real ArUco fiducial. Device round (in progress): ML Kit
v2 + IndicPhotoOCR on Android via Chaquopy, YOLO26n ROIs, and the
real-photo fixture set that produces measured precision/recall — the
golden-report engine and photography protocol are already in the repo
(`core/fixtures/README.md`).

The statutory logic — the part that must never be wrong — is the part that
is finished, deterministic, and tested.
