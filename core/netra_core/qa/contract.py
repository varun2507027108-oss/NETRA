"""Contract v1 conformance validators — the bridge law, executable.

BRIDGE_CONTRACT.md is prose; this module is its enforcement. Three
consumers:
  scripts/check_payload.py        CLI — validate any payload JSON (app
                                  logs, Flutter test fixtures, curl output)
  scripts/record_contract_fixtures.py
                                  records canonical payloads for the
                                  Flutter side to mock against
  tests/test_contract_conformance.py
                                  every payload shape the core emits must
                                  pass, or the suite goes red

Pure stdlib; each validator returns a list of human-readable violations
([] = valid). Shapes are deliberately RE-DECLARED here rather than
derived from schema.py: this polices the contract DOCUMENT, so drift
between docs and serializer surfaces as a test failure.

Laws beyond types (contract sections 4/9):
  - exactly the 17 result keys, always present; optional = null
  - error non-null => verdict RETRY
  - RETRY with error null => quality.prompts non-empty (no silent retries)
  - summary counts match checks[] exactly
  - timings only for canonical stages (s8 is async, never timed)
  - money/quantity field values are STRINGS, never numbers
"""
from __future__ import annotations

import math
import re
from typing import Any

from ..bridge.schema import (ERROR_CODES, RESULT_KEYS, SCHEMA_VERSION,
                             STAGE_NAMES)

VERDICTS = ("PASS", "VIOLATION", "RETRY")
CHECK_STATUS = ("PASS", "FAIL", "NA")
OCR_ENGINES = ("mlkit", "tesseract", "indic", "bhashini")
SHAPES = ("rectangular", "cylindrical", "pouch", "bottle", "blister", "other")
ROIS = ("PACKAGE", "PDP", "BOP", "PRICE", "BARCODE")
SIG_STATUS = ("pending", "signed", "unsupported")
SIG_ERROR_CODES = ("BAD_REQUEST", "NOT_FOUND", "NO_DOSSIER",
                   "ALREADY_SIGNED", "VERIFY_FAILED")

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _num(x) -> bool:
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and math.isfinite(x))


def _int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _bbox(x) -> bool:
    return (isinstance(x, list) and len(x) == 4
            and all(_int(v) for v in x)
            and x[2] > 0 and x[3] > 0 and x[0] >= 0 and x[1] >= 0)


def _finite_numbers(node) -> list:
    bad = []
    if isinstance(node, dict):
        for v in node.values():
            bad += _finite_numbers(v)
    elif isinstance(node, list):
        for v in node:
            bad += _finite_numbers(v)
    elif isinstance(node, float) and not math.isfinite(node):
        bad.append(node)
    return bad


def _keys(obj, required, label, errs, exact=True) -> bool:
    if not isinstance(obj, dict):
        errs.append(f"{label}: must be an object")
        return False
    missing = [k for k in required if k not in obj]
    if missing:
        errs.append(f"{label}: missing keys {missing}")
    extra = [k for k in obj if k not in required] if exact else []
    if exact and extra:
        errs.append(f"{label}: unknown keys {extra}")
    return not missing and (not exact or not extra)


# --------------------------------------------------------------------- scan
def validate_scan_result(r: Any) -> list:
    errs: list = []
    if not isinstance(r, dict):
        return ["payload must be a JSON object"]
    if not _keys(r, RESULT_KEYS, "result", errs):
        return errs
    E = errs.append

    if r["schema_version"] != SCHEMA_VERSION:
        E(f"schema_version: expected {SCHEMA_VERSION}, got "
          f"{r['schema_version']!r}")
    if r["verdict"] not in VERDICTS:
        E(f"verdict: {r['verdict']!r} not in {VERDICTS}")
    for k in ("captured_utc", "completed_utc"):
        if not isinstance(r[k], str) or not _ISO_RE.match(r[k]):
            E(f"{k}: not ISO-8601 UTC ms with Z suffix: {r[k]!r}")
    if not _num(r["total_ms"]) or r["total_ms"] < 0:
        E("total_ms: must be a finite number >= 0")

    tm = r["timings_ms"]
    if not isinstance(tm, dict):
        E("timings_ms: must be an object")
    else:
        for k, v in tm.items():
            if k not in STAGE_NAMES:
                E(f"timings_ms: {k!r} is not a canonical stage "
                  f"(s8 is async, never timed)")
            if not _num(v) or v < 0:
                E(f"timings_ms[{k}]: must be a finite number >= 0")

    q = r["quality"]
    if _keys(q, ("ok", "laplacian_var", "glare_pct", "prompts",
                 "glare_bbox"), "quality", errs):
        if q["ok"] is not None and not isinstance(q["ok"], bool):
            E("quality.ok: must be bool or null")
        for k in ("laplacian_var", "glare_pct"):
            if q[k] is not None and not _num(q[k]):
                E(f"quality.{k}: must be number or null")
        if not isinstance(q["prompts"], list) or \
                not all(isinstance(p, str) for p in q["prompts"]):
            E("quality.prompts: must be a list of strings")
        if q["glare_bbox"] is not None and not _bbox(q["glare_bbox"]):
            E("quality.glare_bbox: must be null or [x, y, w, h] ints")

    g = r["geometry"]
    if g is not None and _keys(g, ("shape", "shape_detected", "mm_per_px",
                                   "pda_cm2", "pda_method", "rois"),
                               "geometry", errs):
        for k in ("shape", "shape_detected"):
            if g[k] is not None and g[k] not in SHAPES:
                E(f"geometry.{k}: {g[k]!r} not in {SHAPES}")
        for k in ("mm_per_px", "pda_cm2"):
            if g[k] is not None and not _num(g[k]):
                E(f"geometry.{k}: must be number or null")
        if g["pda_method"] is not None and \
                not isinstance(g["pda_method"], str):
            E("geometry.pda_method: must be string or null")
        if not isinstance(g["rois"], list):
            E("geometry.rois: must be a list")
        else:
            for i, roi in enumerate(g["rois"]):
                if not _keys(roi, ("roi", "bbox", "conf"),
                             f"geometry.rois[{i}]", errs):
                    continue
                if roi["roi"] not in ROIS:
                    E(f"geometry.rois[{i}].roi: {roi['roi']!r} not in {ROIS}")
                if not _bbox(roi["bbox"]):
                    E(f"geometry.rois[{i}].bbox: must be [x, y, w, h] ints")
                if not _num(roi["conf"]) or not 0.0 <= roi["conf"] <= 1.0:
                    E(f"geometry.rois[{i}].conf: must be 0..1")

    o = r["ocr"]
    if _keys(o, ("engines_used", "tokens"), "ocr", errs):
        if not isinstance(o["engines_used"], list) or \
                not all(e in OCR_ENGINES for e in o["engines_used"]):
            E(f"ocr.engines_used: must be a list from {OCR_ENGINES}")
        if not isinstance(o["tokens"], list):
            E("ocr.tokens: must be a list")
        else:
            for i, t in enumerate(o["tokens"]):
                if not _keys(t, ("text", "bbox", "conf", "engine", "lang"),
                             f"ocr.tokens[{i}]", errs):
                    continue
                if not isinstance(t["text"], str):
                    E(f"ocr.tokens[{i}].text: must be a string")
                if not _bbox(t["bbox"]):
                    E(f"ocr.tokens[{i}].bbox: must be [x, y, w, h] ints")
                if not _num(t["conf"]) or not 0.0 <= t["conf"] <= 1.0:
                    E(f"ocr.tokens[{i}].conf: must be 0..1")
                if t["engine"] not in OCR_ENGINES:
                    E(f"ocr.tokens[{i}].engine: {t['engine']!r} "
                      f"not in {OCR_ENGINES}")

    f = r["fields"]
    if not isinstance(f, dict):
        E("fields: must be an object")
    else:
        for key, fv in f.items():
            label = f"fields[{key!r}]"
            if not _keys(fv, ("raw", "value", "unit", "bbox", "conf"),
                         label, errs):
                continue
            if not isinstance(fv["raw"], str):
                E(f"{label}.raw: must be a string")
            if fv["value"] is not None and not isinstance(fv["value"], str):
                E(f"{label}.value: money/quantities cross the bridge as "
                  f"STRINGS (contract 4.3), got {type(fv['value']).__name__}")
            if fv["unit"] is not None and not isinstance(fv["unit"], str):
                E(f"{label}.unit: must be string or null")
            if fv["bbox"] is not None and not _bbox(fv["bbox"]):
                E(f"{label}.bbox: must be null or [x, y, w, h] ints")
            if not _num(fv["conf"]):
                E(f"{label}.conf: must be a number")

    c = r["checks"]
    if not isinstance(c, list):
        E("checks: must be a list")
    else:
        for i, chk in enumerate(c):
            label = f"checks[{i}]"
            if not _keys(chk, ("rule", "status", "message", "citation",
                               "evidence_bbox"), label, errs):
                continue
            if not isinstance(chk["rule"], str) or not chk["rule"]:
                E(f"{label}.rule: must be a non-empty string")
            if chk["status"] not in CHECK_STATUS:
                E(f"{label}.status: {chk['status']!r} not in {CHECK_STATUS}")
            if not isinstance(chk["message"], str) or not chk["message"]:
                E(f"{label}.message: must be a non-empty string")
            if not isinstance(chk["citation"], str) or not chk["citation"]:
                E(f"{label}.citation: must be a non-empty string")
            if chk["evidence_bbox"] is not None and \
                    not _bbox(chk["evidence_bbox"]):
                E(f"{label}.evidence_bbox: null or [x, y, w, h] ints")

    ex = r["exemption"]
    if ex is not None and _keys(ex, ("exempt", "clause", "note"),
                                "exemption", errs):
        if not isinstance(ex["exempt"], bool):
            E("exemption.exempt: must be a bool")
        if ex["clause"] is not None and not isinstance(ex["clause"], str):
            E("exemption.clause: must be string or null")
        if not isinstance(ex["note"], str):
            E("exemption.note: must be a string")

    s = r["summary"]
    if _keys(s, ("total", "pass", "fail", "na"), "summary", errs):
        for k in ("total", "pass", "fail", "na"):
            if not _int(s[k]) or s[k] < 0:
                E(f"summary.{k}: must be an int >= 0")
        if isinstance(c, list) and _int(s["total"]) and s["total"] != len(c):
            E(f"summary.total: {s['total']} != len(checks) {len(c)}")
        if isinstance(c, list) and all(_int(s[k]) for k in
                                       ("pass", "fail", "na")):
            actual = {st: sum(1 for chk in c
                              if isinstance(chk, dict)
                              and chk.get("status") == st)
                      for st in CHECK_STATUS}
            if (s["pass"], s["fail"], s["na"]) != \
                    (actual["PASS"], actual["FAIL"], actual["NA"]):
                E(f"summary counts do not match checks[]: declared "
                  f"({s['pass']},{s['fail']},{s['na']}) vs actual "
                  f"{tuple(actual[st] for st in CHECK_STATUS)}")

    d = r["dossier"]
    if d is not None and _keys(d, ("sha256", "pdf_path", "signed",
                                   "signature", "cert_pem", "sig_status"),
                               "dossier", errs):
        if not isinstance(d["sha256"], str) or not _HEX64_RE.match(d["sha256"]):
            E("dossier.sha256: must be 64 hex chars")
        if d["pdf_path"] is not None and not isinstance(d["pdf_path"], str):
            E("dossier.pdf_path: must be string or null")
        if not isinstance(d["signed"], bool):
            E("dossier.signed: must be a bool")
        if d["sig_status"] not in SIG_STATUS:
            E(f"dossier.sig_status: {d['sig_status']!r} not in {SIG_STATUS}")

    m = r["meta"]
    if m is not None and _keys(m, ("gps", "device", "options"), "meta", errs):
        for k in ("gps", "device", "options"):
            if m[k] is not None and not isinstance(m[k], dict):
                E(f"meta.{k}: must be an object or null")

    err = r["error"]
    if err is not None:
        if _keys(err, ("code", "message", "stage"), "error", errs):
            if err["code"] not in ERROR_CODES:
                E(f"error.code: {err['code']!r} not in {ERROR_CODES}")
            if not isinstance(err["message"], str):
                E("error.message: must be a string")
            if err["stage"] is not None and not isinstance(err["stage"], str):
                E("error.stage: must be string or null")
        if r["verdict"] != "RETRY":
            E(f"error is set but verdict is {r['verdict']!r} "
              f"(contract 9: errors travel as RETRY)")

    if (r["verdict"] == "RETRY" and err is None and isinstance(q, dict)
            and isinstance(q.get("prompts"), list) and not q.get("prompts")):
        E("RETRY without error must carry quality.prompts guidance "
          "(contract 4.1/9 — no silent retries)")

    nonfinite = _finite_numbers(r)
    if nonfinite:
        E(f"non-finite numbers present: {nonfinite[:3]}")
    return errs


# --------------------------------------------------------------------- ping
def validate_ping(p: Any) -> list:
    errs: list = []
    if not isinstance(p, dict):
        return ["ping payload must be a JSON object"]
    _keys(p, ("schema_version", "core_version", "channel", "capabilities"),
          "ping", errs, exact=False)          # additive growth allowed
    caps = p.get("capabilities")
    if isinstance(caps, dict):
        for k in ("stages_implemented", "stages_planned", "dossier",
                  "signing", "sync", "ocr_engines"):
            if k not in caps:
                errs.append(f"ping.capabilities: missing {k!r}")
        for k in ("stages_implemented", "stages_planned", "ocr_engines"):
            if k in caps and not (isinstance(caps[k], list)
                                  and all(isinstance(v, str)
                                          for v in caps[k])):
                errs.append(f"ping.capabilities.{k}: must be a list of strings")
        for k in ("dossier", "sync"):
            if k in caps and not isinstance(caps[k], bool):
                errs.append(f"ping.capabilities.{k}: must be a bool")
    elif caps is not None:
        errs.append("ping.capabilities: must be an object")
    if p.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"ping.schema_version: expected {SCHEMA_VERSION}")
    return errs


# --------------------------------------------------------------------- sync
def validate_sync_summary(s: Any) -> list:
    errs: list = []
    if not isinstance(s, dict):
        return ["sync summary must be a JSON object"]
    if _keys(s, ("schema_version", "attempted", "synced", "failed",
                 "deferred", "remaining", "offline", "error"), "sync", errs):
        for k in ("attempted", "synced", "failed", "deferred", "remaining"):
            if not _int(s[k]) or s[k] < 0:
                errs.append(f"sync.{k}: must be an int >= 0")
        if not isinstance(s["offline"], bool):
            errs.append("sync.offline: must be a bool")
        if s["error"] is not None and not isinstance(s["error"], str):
            errs.append("sync.error: must be a string or null")
        if s["schema_version"] != SCHEMA_VERSION:
            errs.append(f"sync.schema_version: expected {SCHEMA_VERSION}")
    return errs


# ---------------------------------------------------------------------- sig
def validate_sig_response(s: Any) -> list:
    errs: list = []
    if not isinstance(s, dict):
        return ["signature response must be a JSON object"]
    if _keys(s, ("schema_version", "scan_id", "accepted", "sig_status",
                 "verified", "error"), "sig", errs):
        if not isinstance(s["scan_id"], str):
            errs.append("sig.scan_id: must be a string")
        if not isinstance(s["accepted"], bool):
            errs.append("sig.accepted: must be a bool")
        if s["sig_status"] not in ("pending", "signed"):
            errs.append(f"sig.sig_status: {s['sig_status']!r} "
                        f"not pending/signed")
        if not isinstance(s["verified"], bool):
            errs.append("sig.verified: must be a bool")
        e = s["error"]
        if e is not None:
            if isinstance(e, dict):
                if _keys(e, ("code", "message"), "sig.error", errs):
                    if e["code"] not in SIG_ERROR_CODES:
                        errs.append(f"sig.error.code: {e['code']!r} "
                                    f"not in {SIG_ERROR_CODES}")
                    if not isinstance(e["message"], str):
                        errs.append("sig.error.message: must be a string")
            else:
                errs.append("sig.error: must be an object or null")
    return errs


# -------------------------------------------------------------------- queue
def validate_queue_status(s: Any) -> list:
    errs: list = []
    if not isinstance(s, dict):
        return ["queue status must be a JSON object"]
    if _keys(s, ("schema_version", "total", "pending_sync", "failed",
                 "signed", "dossiers"), "queue", errs):
        for k in ("total", "pending_sync", "failed", "signed", "dossiers"):
            if not _int(s[k]) or s[k] < 0:
                errs.append(f"queue.{k}: must be an int >= 0")
    return errs


KINDS = {
    "scan": validate_scan_result,
    "ping": validate_ping,
    "sync": validate_sync_summary,
    "sig": validate_sig_response,
    "queue": validate_queue_status,
}
