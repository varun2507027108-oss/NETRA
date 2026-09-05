"""Validate a payload JSON against the bridge contract.

    .venv\\Scripts\\python scripts\\check_payload.py --kind scan result.json
    ... --kind ping|sync|sig|queue
    ... -          (read payload from stdin)

Exit 0 = valid; 1 = violations; 2 = unreadable JSON. Use it on anything:
app logs, Antigravity test fixtures, curl output, recorded payloads.
"""
import argparse
import json
import sys

from netra_core.bridge.schema import SCHEMA_VERSION
from netra_core.qa import contract


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kind", choices=sorted(contract.KINDS), default="scan")
    ap.add_argument("path", help="payload JSON file, or '-' for stdin")
    a = ap.parse_args()

    if a.path == "-":
        text = sys.stdin.read()
    else:
        with open(a.path, encoding="utf-8") as fh:
            text = fh.read()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"json parse error: {e}")
        return 2

    errs = contract.KINDS[a.kind](payload)
    if errs:
        for e in errs:
            print(f"violation: {e}")
        print(f"INVALID — contract v{SCHEMA_VERSION} {a.kind} payload")
        return 1
    print(f"VALID — contract v{SCHEMA_VERSION} {a.kind} payload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
