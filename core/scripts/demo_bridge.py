"""Print the contract payloads Antigravity will build against.

Run:  python scripts/demo_bridge.py
"""
import json

from netra_core.bridge.schema import ping_payload
from netra_core.pipeline import run_demo_scan

if __name__ == "__main__":
    print("--- ping ---")
    print(json.dumps(ping_payload(), indent=2))
    print("\n--- scan (demo) ---")
    print(json.dumps(run_demo_scan(), indent=2))
