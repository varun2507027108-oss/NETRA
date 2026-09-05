# NETRA — नेत्र

**Offline-first statutory compliance auditor for pre-packaged commodities.**
SIH26034 · Legal Metrology Act, 2009 · Legal Metrology (Packaged Commodities) Rules, 2011

An inspector photographs a package. NETRA runs a deterministic audit of every
machine-checkable statutory declaration — Table-I font heights, Unit Sale Price
arithmetic, unit syntax, MRP phrasing, PIN codes, country of origin — then files
a cryptographically signed, court-shaped violation dossier that survives
zero-connectivity markets and syncs to the institutional gateway when the
network returns.

## Why

- Tens of millions of retail SKUs; manual inspection covers < 0.01% of packages.
- Violations are sub-visual: 1.2 mm fonts, "gms" instead of "g", a missing
  "incl. of all taxes", ₹/g math that doesn't divide.
- Inspectors need evidence that stands up in court — not a screenshot.

## Pipeline (spec 8 stages — all live on the deterministic engine)

| # | Stage | Function | Live engine | Device-round upgrade | Spec budget |
|---|---|---|---|---|---|
| 1 | s1 quality gate | Laplacian ≥ 100, glare > 242, repositioning prompts | OpenCV | — | < 3 ms |
| 2 | s2 geometry | package silhouette, fiducial-aware crop, shape hint, barcode ROI | classical CV | YOLO26n on LiteRT (PDP/BOP/PRICE ROIs) | ~39 ms |
| 3 | s3 calibration | ArUco homography + solvePnP → mm/px, cylinder unwarp, Rule 7(4) PDA | OpenCV | + TPS pouch correction | ~15 ms |
| 4 | s4 OCR | tier router: first engine with tokens wins | registry + Tesseract (desktop dev tier) | ML Kit v2 + IndicPhotoOCR + Bhashini ULCA | < 1 ms routing |
| 5 | s5 extraction | anchor→value spatial aggregation (L1–L4) | deterministic K-NN heuristics | — | < 1 ms |
| 6 | s6 rule engine | Table-I fonts, glyph aspect, USP math, Rule 6/13/26 | stdlib + Decimal | — | < 1 ms |
| 7 | s7 dossier | evidence PDF, hash chain, §63(4) certificate | ReportLab | platform signing (KeyStore / Secure Enclave) | ~20 ms |
| 8 | s8 sync | offline queue drain, institutional exports | stdlib urllib + SQLite | — | async |

## Evidence chain

image bytes → SHA-256 → dossier PDF → SHA-256 → **hardware-backed ECDSA P-256**
over `"NETRA-DOSSIER-v1|<scan_id>|<pdf_sha256>"` → core verifies → append-only
SQLite WAL ledger → `netra.scan.v1` sync envelope → institutional gateway
(PostgreSQL + PostGIS) → **e-Daakhil / NCH 1915** payloads.

The dossier carries a certificate template under **§63(4), Bharatiya Sakshya
Adhiniyam, 2023** (the provision that replaced §65B(4) of the Indian Evidence
Act). The core never holds private keys; signing happens on the capture device.

## Architecture

```
┌────────────────────────── Flutter (apps/mobile) ──────────────────────────┐
│  scanner UI · report screen · dossier viewer · history · sync banner      │
└───────────────┬──────────────────────────────────────────┬────────────────┘
     MethodChannel "netra.core"                   HTTP 127.0.0.1:8734
     (Android · Chaquopy, in-process)             (desktop / emulator dev)
┌───────────────┴──────────────────────────────────┴────────────────┐
│                   netra_core — the statutory engine               │
│   s1 → s2 → s3 → s4 → s5 → s6 → s7  ·  rules/ (stdlib, tested)   │
│   bridge/schema.py — the frozen JSON contract (v1.2.2)            │
└──────┬───────────────────────────────┬────────────────────────────┘
       │ SQLite WAL evidence ledger    │ s8 sync, when connectivity
       │ (offline queue · append-only) │ returns
┌──────┴──────────┐        ┌──────────┴─────────────────────────────┐
│ dossiers/ (PDF) │        │ netra_backend — institutional gateway  │
│ + ECDSA P-256   │        │ FastAPI · PostgreSQL + PostGIS         │
│ BSA §63(4) cert │        │ /stats /heatmap /export/edakakhil      │
└─────────────────┘        │ /export/nch1915                        │
                           └────────────────────────────────────────┘
```

## Design principles

1. **Deterministic over probabilistic.** The legal decision path is rules +
   `Decimal` arithmetic — 0.45 ms, ~290 unit tests at statutory boundaries
   (PDA band edges, ₹0.01 USP tolerance, the 1-unit exemption, tobacco and
   cement carve-outs). No LLM in the verdict.
2. **Offline-first.** Cloud OCR is a fallback tier, never on the critical
   path; scans complete with zero connectivity.
3. **The rules layer is stdlib-only** — identical code in pytest, in the
   desktop bridge, and inside Chaquopy on Android.
4. **Money and quantities are `Decimal` end-to-end** and cross the bridge as
   strings — no float ever touches statutory arithmetic.
5. **The bridge contract is law** (`docs/BRIDGE_CONTRACT.md`): 17-key result
   schema, always-present keys, in-band errors; Dart renders `checks[]` and
   never re-derives compliance.
6. **Never worse than status quo.** Every CV stage degrades to a no-op when
   unsure — cluttered scene → no crop, no ROI, pipeline proceeds.

## Repo layout

```
core/        netra_core (Python) — pipeline, rules, dossier, sync, bridge
  fixtures/  real-photo validation set + golden-report runner (see README)
  scripts/   demos, fiducial card generator, bench, doctor
backend/     netra_backend — institutional gateway (SQLite / PostGIS)
docs/        BRIDGE_CONTRACT.md, SUBMISSION.md
apps/mobile/ Flutter client (built against the contract)
```

## Quickstart (Windows; POSIX analogous)

```bash
cd core
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pip install -e ..\backend
.venv\Scripts\python scripts\doctor.py          # environment report
.venv\Scripts\pytest                            # ~290 tests
.venv\Scripts\python scripts\demo_dossier.py    # verdict → PDF → signature → ledger
.venv\Scripts\python scripts\demo_sync.py       # ledger → gateway → e-Daakhil/NCH
.venv\Scripts\python scripts\make_fiducial_card.py   # print at 100% scale
.venv\Scripts\bench_pipeline.py --runs 25
.venv\Scripts\python -m netra_core.bridge.server     # desktop bridge, port 8734
```

Tesseract (desktop OCR tier): `winget install UB-Mannheim.TesseractOCR`, or
set `TESSERACT_CMD`. Optional: `pip install -e ".[ocr]"`.

## Status

- 291 tests collected · 289 passing (2 await the desktop OCR binary)
- Statutory core: **0.45 ms** (25-run mean, `scripts/bench_pipeline.py`);
  spec end-to-end target 1.2–1.5 s with on-device ML Kit
- Bridge contract **v1.2.2** — all 8 stages, signing handshake, sync envelope
- Golden-report engine ready; first real-photo precision/recall pending the
  fixture round (`core/fixtures/README.md`)

## Roadmap

1. Real-photo fixture round → measured rule precision/recall
2. On-device OCR (ML Kit v2 + IndicPhotoOCR via the Chaquopy bridge)
3. YOLO26n provider for s2 (PDP/BOP/PRICE ROIs) — drops into the existing
   `run()` surface; contract unchanged
4. Flutter field app (Antigravity, building against `BRIDGE_CONTRACT.md`)
5. TPS unwarping for crumpled pouches (with fixture data)

---
Smart India Hackathon 2025 · Problem SIH26034 · Department of Consumer
Affairs / Legal Metrology Division.
