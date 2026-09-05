"""NETRA fixture runner — real photographs through the full pipeline,
diffed against ground truth (the golden report).

    .venv\\Scripts\\python scripts\\make_fixtures.py
    ... --report-only          (always exit 0)
    ... --psm 6                (dense single-block labels)
    ... --lang eng+hin         (Devanagari, needs hin traineddata)

Reads  core/fixtures/labels_gt.json + images from core/fixtures/labels/,
writes core/fixtures/golden_report.json, prints a console table.

Every fixture = one ScanRequest (shape_hint + dims from ground truth)
through run_scan: s1 quality gate, s3 ArUco calibration, s4 Tesseract
(desktop dev tier), s5 extraction, s6 statutory engine. RETRY outcomes
are CAPTURE problems (blur / fiducial / no text) — re-photograph, don't
re-code. Mismatches split into missing (pipeline missed a violation)
and extra (found more than ground truth says) — inspect the report JSON
to decide: GT gap vs OCR gap vs logic bug.
"""
import argparse
import base64
import json
from pathlib import Path

from netra_core.bridge.schema import scan_request_from_dict
from netra_core.ocr import tesseract_bridge
from netra_core.pipeline import run_scan
from netra_core.qa import golden

ROOT = Path(__file__).resolve().parent.parent
IMAGE_EXTS = (".jpg", ".jpeg", ".png")


def find_image(images_dir: Path, key: str):
    if not images_dir.is_dir():
        return None
    kl = key.lower()
    for p in sorted(images_dir.iterdir()):
        if p.suffix.lower() in IMAGE_EXTS and p.stem.lower() == kl:
            return p
    return None


def _error_outcome(entry: dict, detail: str) -> dict:
    expect = sorted(entry.get("expect_fail") or [])
    return {"status": "error", "verdict": None, "detail": detail,
            "expected_verdict": "VIOLATION" if expect else "PASS",
            "failed_rules": [], "expected_rules": expect,
            "missing_fail": [], "extra_fail": [],
            "fields_ok": [], "fields_missing": [], "fields_mismatch": {},
            "retry_prompts": [], "tokens_decoded": 0, "error": None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gt", default=str(ROOT / "fixtures" / "labels_gt.json"))
    ap.add_argument("--images", default=str(ROOT / "fixtures" / "labels"))
    ap.add_argument("--report",
                    default=str(ROOT / "fixtures" / "golden_report.json"))
    ap.add_argument("--report-only", action="store_true",
                    help="exit 0 even on mismatches")
    ap.add_argument("--psm", type=int, default=11)
    ap.add_argument("--lang", default="eng")
    a = ap.parse_args()

    gt_path, images_dir = Path(a.gt), Path(a.images)
    if not gt_path.exists():
        print(f"ground truth not found: {gt_path}\n"
              f"photograph packages and annotate per "
              f"core/fixtures/README.md")
        return 2
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    if not isinstance(gt, dict) or not gt:
        print("labels_gt.json is empty — nothing to run")
        return 2

    if not tesseract_bridge.available():
        print(tesseract_bridge.INSTALL_HINT)
        return 2
    tesseract_bridge.register(psm=a.psm, lang=a.lang)

    problems, outcomes = [], {}
    for key in sorted(gt):
        entry = gt[key]
        problems += golden.validate_entry(key, entry)
        img = find_image(images_dir, key)
        if img is None:
            outcomes[key] = _error_outcome(
                entry, f"image not found in {images_dir}")
            continue
        b64 = base64.b64encode(img.read_bytes()).decode("ascii")
        body = {"image_b64": b64,
                "shape_hint": entry.get("shape") or "other",
                "options": golden.build_options(entry)}
        request, err = scan_request_from_dict(body)
        if err is not None:
            outcomes[key] = _error_outcome(entry, f"{err['code']}: "
                                                   f"{err['message']}")
            continue
        outcome = golden.compare_fixture(entry, run_scan(request))
        outcome["image"] = str(img)
        outcomes[key] = outcome

    summary = golden.summarize(outcomes)
    report = {"fixtures": outcomes, "summary": summary,
              "gt_problems": problems,
              "tesseract": {"psm": a.psm, "lang": a.lang}}
    report_path = Path(a.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nNETRA fixture report -> {report_path}\n")
    for key, oc in outcomes.items():
        if oc["status"] == "error":
            print(f"{key:<16}ERROR         {oc.get('detail')}")
            continue
        rules = f"{len(oc['failed_rules'])}/{len(oc['expected_rules'])}"
        if oc["missing_fail"]:
            rules += f" miss:{','.join(oc['missing_fail'])}"
        if oc["extra_fail"]:
            rules += f" extra:{','.join(oc['extra_fail'])}"
        n_fields = (len(oc["fields_ok"]) + len(oc["fields_missing"])
                    + len(oc["fields_mismatch"]))
        fields = f"{len(oc['fields_ok'])}/{n_fields}"
        print(f"{key:<16}{oc['status']:<14}{(oc['verdict'] or '-'):<12}"
              f"{rules:<18}{fields}")
    s = summary
    print(f"\nfixtures {s['fixtures']}  ok {s['ok']}  "
          f"mismatch {s['mismatch']}  "
          f"capture_retry {len(s['capture_retry'])}  "
          f"errors {len(s['errors'])}")
    if s["rule_precision"] is not None:
        print(f"rule precision {s['rule_precision']:.0%}  "
              f"recall {s['rule_recall']:.0%}  "
              f"(tp {s['rule_tp']}  fp {s['rule_fp']}  fn {s['rule_fn']})")
    if s["field_extraction_rate"] is not None:
        print(f"field extraction rate {s['field_extraction_rate']:.0%}")
    for p in problems:
        print(f"GT problem: {p}")

    if a.report_only:
        return 0
    return 0 if (s["mismatch"] == 0 and not problems
                 and not s["errors"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
