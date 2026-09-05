"""Record canonical bridge payloads — the Flutter side's mock fixtures.

Writes one JSON per payload shape into core/fixtures/contract/ (commit
these): ping, scan_violation, scan_violation_dossier, scan_retry_blur,
scan_error_decode, sync summaries, attach_signature responses,
queue_status.

Every payload is VALIDATED against netra_core.qa.contract before being
written — a recording that violates the law fails loudly at record time.
scan_id and timestamps vary per recording (regenerate freely); Flutter
tests must not depend on their values. pdf_path in the dossier variant
points at a temporary recording directory — treat it as an opaque string.

Run:  .venv\\Scripts\\python scripts\\record_contract_fixtures.py
"""
from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np

from netra_core import paths
from netra_core.bridge.schema import (SCHEMA_VERSION, ping_payload,
                                      scan_request_from_dict)
from netra_core.dossier import crypto
from netra_core.persistence import queue_db
from netra_core.pipeline import attach_signature, run_demo_scan, run_scan
from netra_core.qa import contract
from netra_core.sync import client as sync_client

ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "fixtures" / "contract"


def record(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.TemporaryDirectory()
    paths.set_data_dir(Path(tmp.name) / "netra")
    queue_db.reset()
    written: dict = {}

    def w(name: str, payload: dict, kind: str) -> None:
        errs = contract.KINDS[kind](payload)
        assert not errs, f"{name} violates the contract: {errs}"
        (out_dir / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8")
        written[name] = kind

    try:
        w("ping.json", ping_payload(), "ping")
        w("scan_violation.json", run_demo_scan(), "scan")
        w("scan_violation_dossier.json", run_demo_scan(dossier=True), "scan")

        ok, buf = cv2.imencode(".jpg", np.zeros((480, 640, 3), np.uint8))
        req, err = scan_request_from_dict({
            "image_b64": base64.b64encode(buf.tobytes()).decode("ascii")})
        assert err is None
        w("scan_retry_blur.json", run_scan(req), "scan")

        req, _ = scan_request_from_dict({"image_b64": "@@@"})
        w("scan_error_decode.json", run_scan(req), "scan")

        class _OK:
            def post(self, url, payload, headers=None, timeout=10.0):
                return 200, {"accepted": True, "duplicate": False}

        run_demo_scan(dossier=True)               # one pending ledger row
        summary = sync_client.SyncClient(
            "http://gateway", transport=_OK()).sync_once().to_dict()
        w("sync_summary_success.json", summary, "sync")
        w("sync_summary_not_configured.json", sync_client.sync_now(), "sync")

        sigs = {
            "bad_request": attach_signature("", "sig", "cert"),
            "not_found": attach_signature("0" * 32, "sig", "cert"),
        }
        if crypto.HAVE_CRYPTO:
            r = run_demo_scan(dossier=True)
            key = crypto.make_dev_key()
            sigs["accepted_verified"] = attach_signature(
                r["scan_id"],
                crypto.dev_sign(key, r["scan_id"],
                                r["dossier"]["sha256"]),
                crypto.make_dev_cert(key))
        for name, resp in sigs.items():
            assert not contract.validate_sig_response(resp), (name, resp)
        (out_dir / "attach_signature_responses.json").write_text(
            json.dumps(sigs, indent=2, ensure_ascii=False), encoding="utf-8")
        written["attach_signature_responses.json"] = "sig"

        w("queue_status.json",
          {"schema_version": SCHEMA_VERSION,
           **queue_db.get_db().status()}, "queue")
    finally:
        queue_db.reset()
        paths.set_data_dir(None)
        try:
            tmp.cleanup()
        except OSError:
            pass
    return written


def main() -> int:
    written = record(OUT_DEFAULT)
    print(f"recorded {len(written)} contract fixtures -> {OUT_DEFAULT}")
    for name, kind in sorted(written.items()):
        print(f"  {name:<38} kind={kind}")
    print("scan_id / timestamps vary per recording — Flutter mocks must not")
    print("depend on their values. Commit these files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
