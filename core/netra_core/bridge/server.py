"""NETRA desktop dev bridge — FastAPI on 127.0.0.1:8734.

Same JSON payloads as the Android MethodChannel. Run:

    python -m netra_core.bridge.server

Endpoints:
    GET  /health            -> ping payload (contract section 6)
    POST /scan              -> ScanRequest JSON -> ScanResult JSON
    POST /scan/demo         -> {tokens?|label?, options?, dossier?} -> result
    POST /attach_signature  -> {scan_id, signature, cert_pem} (contract 8)
    POST /configure         -> {data_dir} — pin the evidence directory
    GET  /queue/status      -> ledger counts (history/sync UI)

Errors travel IN-BAND (error object, verdict RETRY); HTTP status is 200
for every handled pipeline outcome.
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from .. import paths
from ..bridge.schema import SCHEMA_VERSION, error_result, ping_payload, \
    scan_request_from_dict
from ..context import BBox, OCRToken
from ..persistence import queue_db
from ..pipeline import attach_signature as pipeline_attach
from ..pipeline import run_demo_scan, run_scan
from ..sync import client as sync_client

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
    tokens = body.get("tokens")
    if tokens is not None:
        if not isinstance(tokens, list):
            return error_result("BAD_REQUEST", "'tokens' must be a list")
        parsed = []
        for t in tokens:
            if not isinstance(t, dict) or not isinstance(t.get("text"), str):
                return error_result("BAD_REQUEST",
                                    "each token needs a string 'text'")
            parsed.append(OCRToken(
                text=t["text"],
                bbox=BBox.from_list(t.get("bbox") or [0, 0, 10, 10]),
                conf=float(t.get("conf", 1.0)),
                engine=str(t.get("engine", "mlkit")),
                lang=str(t.get("lang", "en")),
            ))
        tokens = parsed
    label = body.get("label")
    if label is not None and not isinstance(label, dict):
        return error_result("BAD_REQUEST", "'label' must be an object")
    options = body.get("options")
    if options is not None and not isinstance(options, dict):
        return error_result("BAD_REQUEST", "'options' must be an object")
    dossier = body.get("dossier")
    if dossier is not None and not isinstance(dossier, bool):
        return error_result("BAD_REQUEST", "'dossier' must be a boolean")
    return run_demo_scan(tokens=tokens, label=label, options=options,
                         dossier=bool(dossier))


@app.post("/attach_signature")
def attach_signature(body: dict) -> dict:
    return pipeline_attach(body.get("scan_id"), body.get("signature"),
                           body.get("cert_pem"))


@app.post("/configure")
def configure(body: dict) -> dict:
    out = {}
    dd = body.get("data_dir")
    if dd is not None:
        if not isinstance(dd, str) or not dd.strip():
            return {"error": {"code": "BAD_REQUEST",
                              "message": "'data_dir' must be a non-empty string"}}
        p = paths.set_data_dir(dd)
        queue_db.reset()
        out.update({"data_dir": str(p), "dossier_dir": str(paths.dossier_dir()),
                    "queue_db": str(paths.queue_db_path())})
    sync_url = body.get("sync_url")
    if sync_url is not None:
        if not isinstance(sync_url, str):
            return {"error": {"code": "BAD_REQUEST",
                              "message": "'sync_url' must be a string"}}
        token = body.get("sync_token")
        if token is not None and not isinstance(token, str):
            return {"error": {"code": "BAD_REQUEST",
                              "message": "'sync_token' must be a string"}}
        sync_client.set_gateway(sync_url, token)
        out["sync_url"] = sync_client.gateway()["url"]
    if not out:
        return {"error": {"code": "BAD_REQUEST",
                          "message": "provide data_dir and/or sync_url"}}
    return out


@app.post("/sync")
def sync() -> dict:
    return sync_client.sync_now()



@app.get("/queue/status")
def queue_status() -> dict:
    return {"schema_version": SCHEMA_VERSION, **queue_db.get_db().status()}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
