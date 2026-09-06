"""Reset NETRA demo state — pre-presentation hygiene.

Clears demo/persistent artifacts so a judge demo starts pristine:
    ~/.netra                 ledger + dossiers (demo_dossier / demo_sync /
                             desktop-bridge scans)
    core/netra_data          demo_dossier / demo_sync output
    core/demo_output         demo_all output (regenerated per run anyway)
    backend/netra_backend.db gateway SQLite, if present

Destructive: deletes EVIDENCE LEDGERS (that is the point — a judge demo
must not open on your last week's queue). Default is dry-run; pass --go
to actually delete. Never touches source, tests, or fixtures.

Run:  .venv\\Scripts\\python scripts\\reset_demo_state.py          (see first)
      .venv\\Scripts\\python scripts\\reset_demo_state.py --go     (wipe)
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = (
    Path.home() / ".netra",
    ROOT / "netra_data",
    ROOT / "demo_output",
    ROOT / "backend" / "netra_backend.db",
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--go", action="store_true",
                    help="actually delete (default: dry-run)")
    a = ap.parse_args()

    for t in TARGETS:
        if not t.exists():
            print(f"[absent ] {t}")
            continue
        if a.go:
            if t.is_dir():
                shutil.rmtree(t)
            else:
                t.unlink()
            print(f"[deleted] {t}")
        else:
            print(f"[present] {t}")
    if not a.go:
        print("\ndry-run — nothing deleted. Re-run with --go to wipe.")
    else:
        print("\ndemo state clean: the next demo_all / scan starts from zero.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
