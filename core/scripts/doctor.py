"""NETRA environment doctor — one command, every dependency, fix hints.

    .venv\\Scripts\\python scripts\\doctor.py

Prints a component table (OK / MISSING + fix), fixture readiness, and the
sync-gateway state. Always exits 0 — it is a report, not a gate.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
IMAGE_EXTS = (".jpg", ".jpeg", ".png")

_ROWS = []


def _check(name: str, fn) -> None:
    try:
        detail = fn()
        status = "OK"
    except Exception as e:                      # noqa: BLE001 — report, not gate
        detail = f"{type(e).__name__}: {e}"
        status = "MISSING"
    _ROWS.append((status, name, detail))


def _import(module: str) -> str:
    importlib.import_module(module)
    return "importable"


def main() -> None:
    _check("python >= 3.9",
           lambda: f"{sys.version.split()[0]}"
           if sys.version_info >= (3, 9) else (_ for _ in ()).throw(
               RuntimeError("too old")))
    _check("numpy", lambda: _import("numpy"))
    _check("opencv", lambda: _import("cv2"))
    _check("reportlab (dossier PDFs)", lambda: _import("reportlab"))
    _check("cryptography (signature verify)",
           lambda: _import("cryptography"))

    def _crypto_flag():
        from netra_core.dossier import crypto
        if not crypto.HAVE_CRYPTO:
            raise RuntimeError("import failed")
        return "ECDSA P-256 verification active"
    _check("netra_core crypto layer", _crypto_flag)

    _check("fastapi + uvicorn (desktop bridge)",
           lambda: (_import("fastapi"), _import("uvicorn"), "ready")[2])
    _check("httpx (bridge tests)", lambda: _import("httpx"))
    _check("pytesseract package", lambda: _import("pytesseract"))

    def _tess():
        from netra_core.ocr import tesseract_bridge
        if not tesseract_bridge.available():
            raise RuntimeError("binary missing (see hint at bottom)")
        return "binary responds — desktop OCR tier ready"
    _check("tesseract binary", _tess)

    def _core():
        import netra_core
        return f"v{netra_core.__version__}"
    _check("netra_core", _core)

    def _backend():
        spec = importlib.util.find_spec("netra_backend")
        if spec is None:
            raise RuntimeError("pip install -e ..\\backend")
        return "importable"
    _check("netra_backend (gateway)", _backend)

    width = max(len(n) for _, n, _ in _ROWS)
    print("NETRA environment doctor\n" + "-" * (width + 40))
    for status, name, detail in _ROWS:
        print(f"[{status:<7}] {name:<{width}}  {detail}")
    missing = [n for s, n, _ in _ROWS if s != "OK"]

    # ---- fixtures -------------------------------------------------------
    print("\nfixtures (real-photo validation set)")
    gt = FIXTURES / "labels_gt.json"
    imgs = FIXTURES / "labels"
    has_entries = False
    if gt.exists() and gt.stat().st_size > 0:
        import json
        try:
            entries = json.loads(gt.read_text(encoding="utf-8"))
            photos = [p for p in imgs.iterdir()
                      if p.suffix.lower() in IMAGE_EXTS] if imgs.is_dir() else []
            keys = {p.stem.lower() for p in photos}
            unmatched = [k for k in entries if k.lower() not in keys]
            print(f"  ground truth: {len(entries)} entries; "
                  f"photos: {len(photos)}; matched: "
                  f"{len(entries) - len(unmatched)}")
            if unmatched:
                print(f"  missing photos for: {', '.join(unmatched[:10])}")
            print(f"  run: .venv\\Scripts\\python scripts\\make_fixtures.py")
            has_entries = True
        except Exception as e:
            print(f"  labels_gt.json parsing error ({e})")
    if not has_entries:
        print("  no labels_gt.json — see core/fixtures/README.md for the")
        print("  photography protocol; even 3 packages unblocks the first")
        print("  golden report")

    # ---- gateway --------------------------------------------------------
    try:
        from netra_core.sync import client
        gw = client.gateway()
        print(f"\nsync gateway: {gw['url'] or 'not configured (call configure with sync_url)'}")
    except Exception:
        pass

    print()
    if missing:
        print(f"{len(missing)} component(s) missing: {', '.join(missing)}")
        try:
            from netra_core.ocr import tesseract_bridge
            if not tesseract_bridge.available():
                print("\ntesseract hint:\n" + tesseract_bridge.INSTALL_HINT)
        except Exception:
            pass
    else:
        print("all components present")


if __name__ == "__main__":
    main()
