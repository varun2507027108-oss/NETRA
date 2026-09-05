"""NETRA — end-to-end evidence-chain demo.

Runs the demo violation scan through the FULL pipeline including Stage 7:
PDF dossier generation, evidence-ledger recording, and — when the
`cryptography` extra is installed — a DEV ECDSA P-256 signature affixed
through the exact attach_signature flow the Android platform uses
(hardware KeyStore in production).

Run:  python scripts/demo_dossier.py
Artifacts land in core/netra_data/ (add it to .gitignore).
"""
import json
from pathlib import Path

from netra_core import paths
from netra_core.dossier import crypto
from netra_core.persistence import queue_db
from netra_core.pipeline import attach_signature, run_demo_scan

DATA = Path(__file__).resolve().parent.parent / "netra_data"
paths.set_data_dir(DATA)

r = run_demo_scan(dossier=True)

print(f"verdict      : {r['verdict']}  "
      f"({r['summary']['fail']} FAIL / {r['summary']['pass']} PASS / "
      f"{r['summary']['na']} NA)")
print(f"scan id      : {r['scan_id']}")
print(f"image sha256 : {r['meta']['device']['model']} capture -> "
      f"{r['checks'][0]['evidence_bbox'] is not None}")
print(f"dossier pdf  : {r['dossier']['pdf_path']}")
print(f"dossier sha  : {r['dossier']['sha256']}")
print(f"sig status   : {r['dossier']['sig_status']}")

if crypto.HAVE_CRYPTO:
    key = crypto.make_dev_key()
    cert = crypto.make_dev_cert(key)
    sig = crypto.dev_sign(key, r["scan_id"], r["dossier"]["sha256"])
    resp = attach_signature(r["scan_id"], sig, cert)
    print(f"signature    : accepted={resp['accepted']} "
          f"verified={resp['verified']} status={resp['sig_status']}")
    if resp["error"]:
        print(f"signature err: {resp['error']}")
else:
    print("signature    : skipped — install netra-core[dev] for the "
          "dev-signing demo")

print(f"ledger       : {json.dumps(queue_db.get_db().status())}")
