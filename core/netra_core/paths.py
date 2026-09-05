"""NETRA filesystem layout.

One writable data directory holds dossier PDFs and the SQLite evidence
ledger. Resolution order: set_data_dir() (Android configure / tests) >
NETRA_DATA_DIR env > ~/.netra. Directories are created lazily.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_override: Optional[Path] = None


def set_data_dir(path) -> Path:
    """Pin the data directory (Android: app-internal storage). None resets."""
    global _override
    _override = Path(path).expanduser() if path is not None else None
    return data_dir()


def data_dir() -> Path:
    if _override is not None:
        p = _override
    elif os.environ.get("NETRA_DATA_DIR"):
        p = Path(os.environ["NETRA_DATA_DIR"])
    else:
        p = Path.home() / ".netra"
    p.mkdir(parents=True, exist_ok=True)
    return p


def dossier_dir() -> Path:
    p = data_dir() / "dossiers"
    p.mkdir(parents=True, exist_ok=True)
    return p


def queue_db_path() -> Path:
    return data_dir() / "netra_queue.db"
