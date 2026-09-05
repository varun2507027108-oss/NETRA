"""Sync client — drains the SQLite evidence ledger to the gateway.

Transport: stdlib urllib (no new core dependencies — this module must
run inside Chaquopy unchanged). A transport is any object with
post(url, payload, headers, timeout) -> (status, body_dict); tests and
the desktop demo inject their own.

Semantics per row (envelope netra.scan.v1, BRIDGE_CONTRACT section 13):
  2xx + accepted  -> mark_synced        (duplicates count: idempotent)
  400/422         -> mark_sync_failed   (server rejected; needs a human)
  5xx / transport -> stays pending, attempt noted, batch stops
Rows are NEVER deleted — the ledger is the system of record; sync_state
only advances (pending -> synced | failed).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from ..bridge.schema import SCHEMA_VERSION
from ..persistence import queue_db

ENVELOPE_KIND = "netra.scan.v1"

_GATEWAY = {"url": None, "token": None}


def set_gateway(url: Optional[str], token: Optional[str] = None) -> None:
    _GATEWAY["url"] = url.rstrip("/") if url else None
    _GATEWAY["token"] = token or None


def gateway() -> dict:
    return dict(_GATEWAY)


@dataclass(frozen=True)
class SyncSummary:
    attempted: int
    synced: int
    failed: int
    deferred: int
    remaining: int
    offline: bool
    error: str = ""

    def to_dict(self) -> dict:
        return {"schema_version": SCHEMA_VERSION,
                "attempted": self.attempted, "synced": self.synced,
                "failed": self.failed, "deferred": self.deferred,
                "remaining": self.remaining, "offline": self.offline,
                "error": self.error or None}


class UrllibTransport:
    def post(self, url, payload, headers=None, timeout=10.0):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return int(resp.status), json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = {}
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                pass
            return int(e.code), body


def envelope_from_row(row: dict) -> dict:
    """Ledger row -> netra.scan.v1 envelope. The device-local dossier PATH
    never leaves the device (privacy; meaningless server-side) — hashes
    and the signature travel instead."""
    try:
        result = json.loads(row.get("result_json") or "null")
    except (json.JSONDecodeError, TypeError):
        result = None
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": ENVELOPE_KIND,
        "scan_id": row["scan_id"],
        "verdict": row["verdict"],
        "created_utc": row.get("created_utc"),
        "image_sha256": row.get("image_sha256"),
        "dossier_sha256": row.get("dossier_sha256"),
        "signature": row.get("signature"),
        "cert_pem": row.get("cert_pem"),
        "sig_verified": bool(row.get("sig_verified")),
        "sig_status": row.get("sig_status") or "pending",
        "attempts": row.get("attempts") or 0,
        "result": result,
    }


class SyncClient:
    def __init__(self, gateway_url, token=None, transport=None,
                 batch_limit: int = 50, timeout: float = 10.0):
        self.ingest_url = gateway_url.rstrip("/") + "/ingest"
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.transport = transport or UrllibTransport()
        self.batch_limit = batch_limit
        self.timeout = timeout

    def sync_once(self) -> SyncSummary:
        db = queue_db.get_db()
        rows = db.pending_sync(limit=self.batch_limit)
        synced = failed = deferred = 0
        offline = False
        error = ""
        for row in rows:
            payload = envelope_from_row(row)
            try:
                status, body = self.transport.post(
                    self.ingest_url, payload, self.headers, self.timeout)
            except Exception as e:                 # offline / DNS / timeout
                db.note_attempt(row["scan_id"], f"{type(e).__name__}: {e}")
                deferred += 1
                offline = True
                error = f"gateway unreachable: {type(e).__name__}: {e}"
                break
            if 200 <= status < 300 and body.get("accepted"):
                db.mark_synced(row["scan_id"])
                synced += 1
            elif status in (400, 422):
                db.mark_sync_failed(row["scan_id"],
                                    f"HTTP {status}: {body}")
                failed += 1
            else:
                db.note_attempt(row["scan_id"], f"HTTP {status}")
                deferred += 1
                error = f"gateway unhealthy: HTTP {status}"
                break
        remaining = db.status()["pending_sync"]
        return SyncSummary(synced + failed + deferred, synced, failed,
                           deferred, remaining, offline, error)


def sync_now(batch_limit: int = 50, transport=None) -> dict:
    """Bridge entrypoint: drain the ledger using the configured gateway."""
    gw = gateway()
    if not gw["url"]:
        return {"schema_version": SCHEMA_VERSION, "attempted": 0, "synced": 0,
                "failed": 0, "deferred": 0,
                "remaining": queue_db.get_db().status()["pending_sync"],
                "offline": False,
                "error": "sync gateway not configured — call configure "
                         "with sync_url"}
    summary = SyncClient(gw["url"], gw["token"], transport=transport,
                         batch_limit=batch_limit).sync_once()
    return summary.to_dict()
