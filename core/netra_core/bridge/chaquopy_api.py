"""NETRA Android entrypoint (Chaquopy).

Kotlin side:
    val py = Python.getInstance()
    val api = py.getModule("netra_core.bridge.chaquopy_api")
    api.callAttr("configure", "{\"data_dir\": \"<app-internal files dir>\"}")
    val resultJson = api.callAttr("scan", requestJson).toString()

Pure JSON-in / JSON-out (contract v1.1) — only the transport differs from
the desktop HTTP bridge. configure() pins the evidence directory to
app-internal storage BEFORE the first scan (Android 10+ scoped storage).
"""
from __future__ import annotations

import json

from .. import paths
from ..bridge.schema import SCHEMA_VERSION, error_result, ping_payload, \
    scan_request_from_dict
from ..persistence import queue_db
from ..sync import client as sync_client

_SIG_ERR = {"schema_version": SCHEMA_VERSION, "scan_id": "",
            "accepted": False, "sig_status": "pending", "verified": False,
            "error": None}


def scan(request_json: str) -> str:
    from ..pipeline import run_scan    # lazy: vision deps stay out of the
    try:                               # ping/configure/queue_status paths
        body = json.loads(request_json)
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps(error_result("BAD_REQUEST", f"invalid JSON: {e}"))
    request, err = scan_request_from_dict(body)
    if err is not None:
        return json.dumps(error_result(err["code"], err["message"]))
    return json.dumps(run_scan(request))


def ping() -> str:
    return json.dumps(ping_payload())


def configure(config_json: str) -> str:
    try:
        body = json.loads(config_json)
        if not isinstance(body, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError, TypeError):
        return json.dumps({"error": {"code": "BAD_REQUEST",
                                     "message": "invalid JSON"}})
    out = {}
    dd = body.get("data_dir")
    if dd is not None:
        if not isinstance(dd, str) or not dd.strip():
            return json.dumps({"error": {"code": "BAD_REQUEST",
                                         "message": "'data_dir' required"}})
        p = paths.set_data_dir(dd)
        queue_db.reset()
        out.update({"data_dir": str(p),
                    "dossier_dir": str(paths.dossier_dir()),
                    "queue_db": str(paths.queue_db_path())})
    sync_url = body.get("sync_url")
    if sync_url is not None:
        if not isinstance(sync_url, str):
            return json.dumps({"error": {"code": "BAD_REQUEST",
                                         "message": "'sync_url' must be a string"}})
        sync_client.set_gateway(sync_url, body.get("sync_token")
                                if isinstance(body.get("sync_token"), str)
                                else None)
        out["sync_url"] = sync_client.gateway()["url"]
    if not out:
        return json.dumps({"error": {"code": "BAD_REQUEST",
                                     "message": "provide data_dir and/or sync_url"}})
    return json.dumps(out)


def attach_signature(body_json: str) -> str:
    from ..pipeline import attach_signature as pipeline_attach   # lazy
    try:
        body = json.loads(body_json)
        if not isinstance(body, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError, TypeError):
        out = dict(_SIG_ERR)
        out["error"] = {"code": "BAD_REQUEST", "message": "invalid JSON"}
        return json.dumps(out)
    return json.dumps(pipeline_attach(body.get("scan_id"),
                                      body.get("signature"),
                                      body.get("cert_pem")))


def queue_status() -> str:
    return json.dumps({"schema_version": SCHEMA_VERSION,
                       **queue_db.get_db().status()})


def sync_now() -> str:
    return json.dumps(sync_client.sync_now())
