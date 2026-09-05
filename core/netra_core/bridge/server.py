"""NETRA desktop dev bridge — FastAPI on 127.0.0.1:8734.

Same JSON payloads as the Android MethodChannel: Flutter Windows dev
points NetraBridge at HTTP, Android uses Chaquopy. Run:

    python -m netra_core.bridge.server

Endpoints:
    GET  /health        -> ping payload (contract section 5)
    POST /scan          -> ScanRequest JSON -> ScanResult JSON
    POST /scan/demo     -> optional {label?, options?} -> full demo result
    POST /attach_signature -> 501 until s7_dossier lands

Errors are carried IN-BAND (error object, verdict RETRY); the HTTP status
is 200 for every handled pipeline outcome.
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from ..pipeline import run_demo_scan, run_scan
from .schema import error_result, ping_payload, scan_request_from_dict

HOST, PORT = "127.0.0.1", 8734

app = FastAPI(title="NETRA bridge", version="0.1.0",
              docs_url=None, redoc_url=None)


@app.get("/health")
def health() -> dict:
    return ping_payload()


@app.post("/scan")
def scan(body: dict) -> dict:
    request, err = scan_request_from_dict(body)
    if err is not None:
        return error_result(err["code"], err["message"])
    return run_scan(request)


@app.post("/scan/demo")
def scan_demo(body: dict | None = None) -> dict:
    body = body or {}
    label = body.get("label")
    if label is not None and not isinstance(label, dict):
        return error_result("BAD_REQUEST", "'label' must be an object")
    options = body.get("options")
    if options is not None and not isinstance(options, dict):
        return error_result("BAD_REQUEST", "'options' must be an object")
    return run_demo_scan(label, options)


@app.post("/attach_signature")
def attach_signature(body: dict) -> dict:
    return error_result("STAGE_FAILURE",
                        "attach_signature is reserved until s7_dossier lands",
                        stage="s7_dossier")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
