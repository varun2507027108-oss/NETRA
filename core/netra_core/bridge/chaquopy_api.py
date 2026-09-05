"""NETRA Android entrypoint (Chaquopy).

Kotlin side:
    val py = Python.getInstance()
    val api = py.getModule("netra_core.bridge.chaquopy_api")
    val resultJson = api.callAttr("scan", requestJson).toString()

Pure JSON-in / JSON-out (contract v1), so it is fully unit-testable
off-device; only the *transport* differs from the desktop HTTP bridge.
"""
from __future__ import annotations

import json

from ..pipeline import run_scan
from .schema import error_result, ping_payload, scan_request_from_dict


def scan(request_json: str) -> str:
    try:
        body = json.loads(request_json)
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps(error_result("BAD_REQUEST", f"invalid JSON: {e}"))
    request, err = scan_request_from_dict(body)
    if err is not None:
        return json.dumps(error_result(err["code"], err["message"]))
    return json.dumps(run_scan(request))


def ping() -> str:
    return json.dumps(ping_payload())
