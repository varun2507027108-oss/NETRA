r"""NETRA — the full eight-stage story in one command (judge demo).

    .venv\Scripts\python scripts\demo_all.py

Runs the complete narrative in a CLEAN state (demo_output/ wiped at
start): planted-trap scan -> statutory verdict -> signed dossier PDF
(kept at demo_output/netra/dossiers/ — open it) -> ECDSA signature
verified -> offline ledger -> sync drain into the in-process
institutional gateway -> violation stats -> e-Daakhil & NCH payloads
-> the latency numbers.

Engine-independent: uses the s4 dev-injection path, so it runs on any
machine with just `pip install -e "core[dev]"` — no tesseract, no
camera, no network (the "gateway" is in-process). Phases 5-7 need
`pip install -e ..\backend` and degrade gracefully without it.
"""
from __future__ import annotations

import json
import shutil
import statistics
from pathlib import Path
from urllib.parse import urlparse

from netra_core import paths
from netra_core.bridge.schema import ping_payload
from netra_core.dossier import crypto
from netra_core.persistence import queue_db
from netra_core.pipeline import attach_signature, run_demo_scan
from netra_core.sync import client as sync_client

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo_output"


def hr(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 58 - len(title)))


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    paths.set_data_dir(OUT / "netra")
    queue_db.reset()

    p = ping_payload()
    caps = p["capabilities"]
    hr("NETRA — capabilities")
    print(f"core {p['core_version']} · bridge contract v{p['schema_version']}")
    print(f"stages live: {', '.join(caps['stages_implemented'])} + s8_sync")

    hr("1 · THE SCAN — five planted statutory traps")
    r = run_demo_scan(dossier=True)
    print(f"verdict: {r['verdict']}   ({r['summary']['fail']} FAIL / "
          f"{r['summary']['pass']} PASS / {r['summary']['na']} NA · "
          f"{r['total_ms']:.1f} ms)")
    for c in r["checks"]:
        if c["status"] == "FAIL":
            print(f"  [FAIL] Rule {c['rule']:<8} {c['message'][:88]}")

    hr("2 · THE DOSSIER — court-shaped evidence document")
    d = r["dossier"]
    print(f"pdf    : {d['pdf_path']}")
    print(f"sha256 : {d['sha256']}")
    print("open it: red evidence boxes, citations under every finding,")
    print("         the BSA section 63(4) certificate page")

    hr("3 · THE SIGNATURE — hardware-backed ECDSA P-256 (dev key here)")
    if crypto.HAVE_CRYPTO:
        key = crypto.make_dev_key()
        resp = attach_signature(
            r["scan_id"],
            crypto.dev_sign(key, r["scan_id"], d["sha256"]),
            crypto.make_dev_cert(key))
        print(f"payload: NETRA-DOSSIER-v1|{r['scan_id']}|{d['sha256'][:16]}...")
        print(f"result : accepted={resp['accepted']} verified="
              f"{resp['verified']} status={resp['sig_status']}")
        print("on Android this key lives in the KeyStore and never leaves it")
    else:
        print("cryptography extra not installed — phase skipped")

    hr("4 · THE OFFLINE LEDGER — zero-connectivity field reality")
    print(f"ledger : {json.dumps(queue_db.get_db().status())}")
    print("scans complete with no network; the queue drains when it returns")

    try:
        from fastapi.testclient import TestClient
        from netra_backend import db
        from netra_backend.app import app
    except Exception:
        hr("5-7 · INSTITUTIONAL GATEWAY — backend not installed")
        print('pip install -e "..\\backend" to enable the sync + export phases')
        return 0

    db.reset(f"sqlite:///{OUT}/gateway.db")
    api = TestClient(app)

    class Transport:
        def post(self, url, payload, headers=None, timeout=10.0):
            resp = api.post(urlparse(url).path, json=payload)
            return resp.status_code, resp.json()

    hr("5 · THE SYNC — ledger drain (idempotent, append-only)")
    s = sync_client.SyncClient("http://gateway",
                               transport=Transport()).sync_once()
    print(f"sync   : synced={s.synced} failed={s.failed} "
          f"deferred={s.deferred} remaining={s.remaining}")

    hr("6 · THE INSTITUTION — violation density for route planning")
    st = api.get("/stats").json()
    top = ", ".join(f"Rule {t['rule']} x{t['count']}"
                    for t in st["top_rules"][:3])
    print(f"gateway: {st['total']} scan(s), {st['violation']} violation(s), "
          f"{st['signed']} signed, {st['located']} geo-located")
    print(f"top rules: {top}")
    hm = api.get("/heatmap").json()
    print(f"heatmap: {len(hm['features'])} GeoJSON point(s) "
          f"(PostGIS in production)")

    hr("7 · THE EXPORTS — e-Daakhil & NCH 1915 payloads")
    ed = api.post(f"/export/edakakhil/{r['scan_id']}").json()
    print(f"e-Daakhil: respondent {ed['case']['respondent']['name']!r}, "
          f"{len(ed['case']['violations'])} violations, evidence sha "
          f"{ed['case']['evidence']['dossier_sha256'][:16]}...")
    nch = api.post(f"/export/nch1915/{r['scan_id']}").json()
    print(f"NCH 1915 : pin zone {nch['complaint']['pin_zone']}")

    hr("8 · THE NUMBERS — deterministic statutory core")
    rows = [run_demo_scan() for _ in range(25)]
    core = [x["timings_ms"]["s5_field_extract"]
            + x["timings_ms"]["s6_metrology"] for x in rows]
    print(f"statutory core (s5+s6, 25-run mean): {statistics.mean(core):.2f} ms")
    print("spec end-to-end target: 1.2-1.5 s with on-device ML Kit OCR")

    db.dispose()
    print(f"\nartifacts kept in {OUT} — the dossier PDF survives this script")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
