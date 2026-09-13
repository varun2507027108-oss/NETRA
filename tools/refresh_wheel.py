#!/usr/bin/env python3
"""
tools/refresh_wheel.py — Build fresh netra_core wheel, deploy to Android app,
and verify critical package contents to prevent silent stale-wheel regressions.
"""

import os
import sys
import shutil
import zipfile
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "core"
APP_DIR = REPO_ROOT / "apps" / "mobile" / "android" / "app"
WHEEL_NAME = "netra_core-0.1.0-py3-none-any.whl"
TARGET_WHEEL = APP_DIR / WHEEL_NAME


def main():
    print(f"[*] Building fresh wheel in {CORE_DIR}...")
    dist_dir = CORE_DIR / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(dist_dir)]
    res = subprocess.run(cmd, cwd=CORE_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        print("[!] pip wheel build failed:")
        print(res.stderr)
        sys.exit(1)
        
    built_wheel = dist_dir / WHEEL_NAME
    if not built_wheel.exists():
        wheels = list(dist_dir.glob("netra_core-*.whl"))
        if not wheels:
            print(f"[!] No wheel found in {dist_dir}")
            sys.exit(1)
        built_wheel = sorted(wheels, key=os.path.getmtime)[-1]
        
    print(f"[*] Copying {built_wheel.name} to {TARGET_WHEEL}...")
    shutil.copy2(built_wheel, TARGET_WHEEL)
    
    print("[*] Verifying wheel contents...")
    with zipfile.ZipFile(TARGET_WHEEL, "r") as z:
        namelist = z.namelist()
        
        # 1. vision_config.json contains "yolo"
        vc_name = [n for n in namelist if n.endswith("vision_config.json")]
        if not vc_name:
            print("[!] FAIL: vision_config.json missing from wheel!")
            sys.exit(1)
        cfg = json.loads(z.read(vc_name[0]).decode("utf-8"))
        if "yolo" not in cfg:
            print("[!] FAIL: vision_config.json does not contain 'yolo' section!")
            sys.exit(1)
        print("  [+] vision_config.json contains 'yolo' section: PASS")
        
        # 2. stages/s2_roi_merge.py exists
        if not any(n.endswith("stages/s2_roi_merge.py") for n in namelist):
            print("[!] FAIL: stages/s2_roi_merge.py missing from wheel!")
            sys.exit(1)
        print("  [+] stages/s2_roi_merge.py present: PASS")
        
        # 3. bridge/schema.py contains "roi_boxes"
        schema_name = [n for n in namelist if n.endswith("bridge/schema.py")]
        if not schema_name:
            print("[!] FAIL: bridge/schema.py missing from wheel!")
            sys.exit(1)
        schema_src = z.read(schema_name[0]).decode("utf-8")
        if "roi_boxes" not in schema_src:
            print("[!] FAIL: bridge/schema.py missing 'roi_boxes' definition!")
            sys.exit(1)
        print("  [+] bridge/schema.py contains 'roi_boxes': PASS")
        
    print(f"[+] Wheel successfully refreshed and verified: {TARGET_WHEEL} ({TARGET_WHEEL.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
