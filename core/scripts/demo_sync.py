"""NETRA — end-to-end Stage 8 demo: ledger -> gateway -> exports.

Runs the demo violation scan (dossier + dev signature), drains the
evidence ledger through SyncClient into an in-process institutional
gateway, then prints stats, the located-violation count, and a sample
e-Daakhil export. Nothing persists (temp dirs).

Run (after installing the backend):
    python scripts/demo_sync.py
"""
import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from netra_backend import db
from netra_backend.app import app
from netra_core import paths
from netra_core.dossier import crypto
from netra_core.persistence import queue_db
from netra_core.pipeline import attach_signature, run_demo_scan
from netra_core.sync import client


def main() -> None:
    tmp = tempfile.TemporaryDirectory()
    paths.set_data_dir(Path(tmp.name) / "netra")
    queue_db.reset()
    db.reset(f"sqlite:///{tmp.name}/backend.db")
    api = TestClient(app)

    class Transport:
        def post(self, url, payload, headers=None, timeout=10.0):
            resp = api.post(urlparse(url).path, json=payload)
            return resp.status_code, resp.json()

    r = run_demo_scan(dossier=True)
    print(f"scan        : {r['scan_id']}  verdict {r['verdict']} "
          f"({r['summary']['fail']} FAIL)")
    if crypto.HAVE_CRYPTO:
        key = crypto.make_dev_key()
        attach_signature(r["scan_id"],
                         crypto.dev_sign(key, r["scan_id"],
                                         r["dossier"]["sha256"]),
                         crypto.make_dev_cert(key))
        print("signature   : attached (dev key, ECDSA P-256)")
    print(f"ledger      : {json.dumps(queue_db.get_db().status())}")

    s = client.SyncClient("http://gateway", transport=Transport()).sync_once()
    print(f"sync        : synced={s.synced} failed={s.failed} "
          f"deferred={s.deferred} remaining={s.remaining}")

    print(f"gateway     : {json.dumps(api.get('/stats').json())}")
    hm = api.get("/heatmap").json()
    print(f"heatmap     : {len(hm['features'])} located violation(s)")

    exp = api.post(f"/export/edakakhil/{r['scan_id']}").json()
    print(f"e-Daakhil   : respondent {exp['case']['respondent']['name']!r}, "
          f"{len(exp['case']['violations'])} violations, dossier sha "
          f"{exp['case']['evidence']['dossier_sha256'][:16]}...")
    nch = api.post(f"/export/nch1915/{r['scan_id']}").json()
    print(f"NCH 1915    : pin zone {nch['complaint']['pin_zone']}")

    db.dispose()
    queue_db.get_db().close()
    queue_db.reset()
    try:
        tmp.cleanup()
    except OSError:
        pass


if __name__ == "__main__":
    main()
