"""SQLite ACID evidence ledger (WAL) — the s8 sync substrate, driven today
by the pipeline (record_scan / update_result) and the signing handshake
(attach_signature). One row per COMPLETED audit scan (PASS / VIOLATION;
RETRY never lands here — it is repositioning noise, not evidence).

Thread-safe: one connection, check_same_thread=False + a lock (FastAPI
sync handlers run in a threadpool). Cached process-wide via get_db();
tests and configure() reset the handle.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from .. import paths

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    scan_id        TEXT PRIMARY KEY,
    created_utc    TEXT NOT NULL,
    verdict        TEXT NOT NULL,
    image_sha256   TEXT,
    dossier_sha256 TEXT,
    dossier_path   TEXT,
    result_json    TEXT,
    signature      TEXT,
    cert_pem       TEXT,
    signed_utc     TEXT,
    sig_verified   INTEGER NOT NULL DEFAULT 0,
    sig_status     TEXT NOT NULL DEFAULT 'pending',
    sync_state     TEXT NOT NULL DEFAULT 'pending',
    synced_utc     TEXT,
    attempts       INTEGER NOT NULL DEFAULT 0,
    last_attempt_utc TEXT,
    last_error     TEXT
);
"""

# Columns added after the first release; applied to existing ledgers.
_MIGRATIONS = (
    ("attempts", "ALTER TABLE scans ADD COLUMN attempts "
                 "INTEGER NOT NULL DEFAULT 0"),
    ("last_attempt_utc", "ALTER TABLE scans ADD COLUMN last_attempt_utc TEXT"),
    ("last_error", "ALTER TABLE scans ADD COLUMN last_error TEXT"),
)


def _migrate(conn) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(scans)")}
    for name, ddl in _MIGRATIONS:
        if name not in cols:
            conn.execute(ddl)
    conn.commit()


_LOCK = threading.Lock()
_DB: Optional["QueueDB"] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds") \
        .replace("+00:00", "Z")


class QueueDB:
    def __init__(self, path):
        self.closed = False
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")   # ACID durability
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
            _migrate(self._conn)

    # ---- writes --------------------------------------------------------
    def record_scan(self, scan_id: str, verdict: str, *,
                    image_sha256: Optional[str] = None,
                    dossier_sha256: Optional[str] = None,
                    dossier_path: Optional[str] = None) -> None:
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO scans (scan_id, created_utc, verdict, "
                    "image_sha256, dossier_sha256, dossier_path) "
                    "VALUES (?,?,?,?,?,?)",
                    (scan_id, _now(), verdict, image_sha256,
                     dossier_sha256, dossier_path))
                self._conn.commit()
            except sqlite3.IntegrityError:
                pass                        # same scan recorded twice: keep first

    def update_result(self, scan_id: str, result: dict) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE scans SET result_json=? WHERE scan_id=?",
                (json.dumps(result, ensure_ascii=False), scan_id))
            self._conn.commit()

    def attach_signature(self, scan_id: str, signature: str, cert_pem: str,
                         verified: bool) -> bool:
        """Flip to signed; keep result_json's dossier object in sync."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE scans SET signature=?, cert_pem=?, signed_utc=?, "
                "sig_verified=?, sig_status='signed' WHERE scan_id=?",
                (signature, cert_pem, _now(), int(verified), scan_id))
            row = self._conn.execute(
                "SELECT result_json FROM scans WHERE scan_id=?",
                (scan_id,)).fetchone()
            if row and row["result_json"]:
                try:
                    result = json.loads(row["result_json"])
                    if isinstance(result.get("dossier"), dict):
                        result["dossier"].update(
                            {"signed": True, "signature": signature,
                             "cert_pem": cert_pem, "sig_status": "signed"})
                        self._conn.execute(
                            "UPDATE scans SET result_json=? WHERE scan_id=?",
                            (json.dumps(result, ensure_ascii=False), scan_id))
                except json.JSONDecodeError:
                    pass
            self._conn.commit()
            return cur.rowcount == 1

    def mark_synced(self, scan_id: str) -> None:      # s8
        with self._lock:
            self._conn.execute(
                "UPDATE scans SET sync_state='synced', synced_utc=? "
                "WHERE scan_id=?", (_now(), scan_id))
            self._conn.commit()

    def note_attempt(self, scan_id: str, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE scans SET attempts=attempts+1, last_attempt_utc=?, "
                "last_error=? WHERE scan_id=? AND sync_state='pending'",
                (_now(), error, scan_id))
            self._conn.commit()

    def mark_sync_failed(self, scan_id: str, error: str) -> None:
        """Server rejected the envelope (400/422): permanent, needs a human."""
        with self._lock:
            self._conn.execute(
                "UPDATE scans SET sync_state='failed', attempts=attempts+1, "
                "last_attempt_utc=?, last_error=? WHERE scan_id=?",
                (_now(), error, scan_id))
            self._conn.commit()

    # ---- reads ---------------------------------------------------------
    def get_scan(self, scan_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM scans WHERE scan_id=?", (scan_id,)).fetchone()
        return dict(row) if row is not None else None

    def pending_sync(self, limit=None) -> list:
        sql = ("SELECT * FROM scans WHERE sync_state='pending' "
               "ORDER BY created_utc")
        params = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (int(limit),)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def status(self) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS total,"
                " COALESCE(SUM(sync_state='pending'),0) AS pending_sync,"
                " COALESCE(SUM(sync_state='failed'),0) AS failed,"
                " COALESCE(SUM(sig_status='signed'),0) AS signed,"
                " COALESCE(SUM(dossier_sha256 IS NOT NULL),0) AS dossiers"
                " FROM scans").fetchone()
        return {k: int(row[k]) for k in row.keys()}

    def close(self) -> None:
        with self._lock:
            if not self.closed:
                self._conn.close()
                self.closed = True


def get_db() -> QueueDB:
    global _DB
    with _LOCK:
        if _DB is None or _DB.closed:
            _DB = QueueDB(paths.queue_db_path())
        return _DB


def reset() -> None:
    """Drop the cached handle (tests, configure/data-dir switches)."""
    global _DB
    with _LOCK:
        if _DB is not None and not _DB.closed:
            _DB.close()
        _DB = None
