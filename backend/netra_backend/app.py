"""NETRA institutional gateway — the cloud side of spec Stage 8.

Receives netra.scan.v1 envelopes drained from field devices
(netra_core.sync.SyncClient), stores them append-only, and exposes:

    POST /ingest                idempotent envelope intake
    GET  /scans                 list (verdict filter, pagination)
    GET  /scans/{scan_id}       full stored record
    GET  /stats                 counts + top violated rules
    GET  /heatmap               GeoJSON of located scans
    POST /export/edakakhil/{id} standardized e-Daakhil payload
    POST /export/nch1915/{id}   standardized NCH 1915 payload

PostgreSQL + PostGIS in production (DATABASE_URL + [postgres] extra);
SQLite for dev/demo — identical API surface. Run:

    uvicorn netra_backend.app:app --port 8735
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from netra_core.dossier import crypto
from netra_core.qa import contract as contract_qa
from netra_core.sync.exporters import edakakhil_payload, nch1915_payload

from . import db
from .models import ScanRecord

app = FastAPI(title="NETRA institutional gateway", version="0.1.0")


def _gateway_token() -> str:
    return os.environ.get("NETRA_GATEWAY_TOKEN", "")


def require_auth(authorization: str = Header(default="")) -> None:
    token = _gateway_token()
    if not token:
        return                      # dev mode: open, documented
    if authorization != f"Bearer {token}":
        raise HTTPException(401, "invalid or missing gateway token")


_origins = [o.strip() for o in
            os.environ.get("NETRA_CORS_ORIGINS", "*").split(",") if o.strip()]
if not _origins:
    _origins = ["*"]

app.add_middleware(CORSMiddleware, allow_origins=_origins,
                   allow_methods=["*"], allow_headers=["*"])

_VERDICTS = ("PASS", "VIOLATION")


def get_db():
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds") \
        .replace("+00:00", "Z")


def _validate(env) -> tuple:
    if not isinstance(env, dict):
        return 400, "envelope must be a JSON object"
    sid = env.get("scan_id")
    if not isinstance(sid, str) or not sid:
        return 400, "scan_id is required"
    verdict = env.get("verdict")
    if not verdict:
        return 400, "verdict is required"
    if verdict not in _VERDICTS:
        return 422, ("verdict must be PASS or VIOLATION "
                     "(RETRY scans are never recorded or synced)")
    if not isinstance(env.get("result"), dict):
        return 422, "result (contract ScanResult object) is required"
    return None


@app.post("/ingest")
def ingest(envelope: dict, session=Depends(get_db),
           _auth=Depends(require_auth)):
    err = _validate(envelope)
    if err:
        raise HTTPException(status_code=err[0], detail=err[1])
    if envelope.get("kind") != "netra.scan.v1":
        raise HTTPException(422, "kind must be netra.scan.v1")
    errs = contract_qa.validate_scan_result(envelope.get("result"))
    if errs:
        raise HTTPException(422, f"result violates bridge contract: {errs[0]}")

    if session.get(ScanRecord, envelope["scan_id"]) is not None:
        return {"accepted": True, "duplicate": True,
                "scan_id": envelope["scan_id"]}

    # server-side verification — the client's sig_verified is never trusted
    sig_verified = False
    if (envelope.get("signature") and envelope.get("cert_pem")
            and envelope.get("dossier_sha256")):
        verified, verr = crypto.verify_signature(
            envelope["scan_id"], envelope["dossier_sha256"],
            envelope["signature"], envelope["cert_pem"])
        if verr is not None:            # definite failure, not "unavailable"
            raise HTTPException(422, f"signature invalid: {verr}")
        sig_verified = verified

    gps = ((envelope.get("result") or {}).get("meta") or {}).get("gps") or {}
    lat, lon = gps.get("lat"), gps.get("lon")
    rec = ScanRecord(
        scan_id=envelope["scan_id"], verdict=envelope["verdict"],
        created_utc=envelope.get("created_utc"), received_utc=_now(),
        image_sha256=envelope.get("image_sha256"),
        dossier_sha256=envelope.get("dossier_sha256"),
        signature=envelope.get("signature"),
        cert_pem=envelope.get("cert_pem"),
        sig_verified=sig_verified,
        sig_status=envelope.get("sig_status") or "pending",
        lat=float(lat) if isinstance(lat, (int, float)) else None,
        lon=float(lon) if isinstance(lon, (int, float)) else None,
        result_json=json.dumps(envelope.get("result"), ensure_ascii=False),
        attempts=int(envelope.get("attempts") or 0))
    if db.postgis_enabled() and rec.lat is not None and rec.lon is not None:
        from geoalchemy2.elements import WKTElement
        rec.location = WKTElement(f"POINT({rec.lon} {rec.lat})", srid=4326)
    session.add(rec)
    session.commit()
    return {"accepted": True, "duplicate": False, "scan_id": rec.scan_id}


@app.get("/scans")
def list_scans(verdict: str = None, limit: int = 50, offset: int = 0,
               session=Depends(get_db)):
    q = session.query(ScanRecord)
    if verdict:
        q = q.filter(ScanRecord.verdict == verdict)
    rows = q.order_by(ScanRecord.received_utc.desc()) \
            .offset(max(0, offset)).limit(max(1, min(limit, 500))).all()
    out = []
    for r in rows:
        try:
            summary = (json.loads(r.result_json) or {}).get("summary") or {}
        except json.JSONDecodeError:
            summary = {}
        out.append({"scan_id": r.scan_id, "verdict": r.verdict,
                    "created_utc": r.created_utc,
                    "received_utc": r.received_utc,
                    "sig_status": r.sig_status,
                    "fail": summary.get("fail")})
    return out


@app.get("/scans/{scan_id}")
def get_scan(scan_id: str, session=Depends(get_db)):
    rec = session.get(ScanRecord, scan_id)
    if rec is None:
        raise HTTPException(404, "unknown scan_id")
    try:
        result = json.loads(rec.result_json)
    except json.JSONDecodeError:
        result = None
    return {"scan_id": rec.scan_id, "verdict": rec.verdict,
            "created_utc": rec.created_utc,
            "received_utc": rec.received_utc,
            "image_sha256": rec.image_sha256,
            "dossier_sha256": rec.dossier_sha256,
            "sig_status": rec.sig_status,
            "sig_verified": rec.sig_verified,
            "lat": rec.lat, "lon": rec.lon, "attempts": rec.attempts,
            "result": result}


@app.get("/stats")
def stats(session=Depends(get_db)):
    # SQL aggregation for headline counts
    total = session.query(func.count(ScanRecord.scan_id)).scalar() or 0
    violation_cnt = session.query(func.count(ScanRecord.scan_id)).filter(ScanRecord.verdict == "VIOLATION").scalar() or 0
    pass_cnt = total - violation_cnt
    signed_cnt = session.query(func.count(ScanRecord.scan_id)).filter(ScanRecord.sig_status == "signed").scalar() or 0
    located_cnt = session.query(func.count(ScanRecord.scan_id)).filter(ScanRecord.lat.isnot(None)).scalar() or 0

    counts = {"total": total, "violation": violation_cnt, "pass": pass_cnt,
              "signed": signed_cnt, "located": located_cnt}

    # Top rules parsed from VIOLATION rows only (until rule-column DB migration)
    rule_counts: dict = {}
    v_rows = session.query(ScanRecord.result_json).filter(ScanRecord.verdict == "VIOLATION").all()
    for (r_json,) in v_rows:
        try:
            for c in (json.loads(r_json) or {}).get("checks") or []:
                if c.get("status") == "FAIL":
                    rule_counts[c.get("rule")] = \
                        rule_counts.get(c.get("rule"), 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    top = [{"rule": k, "count": v} for k, v in
           sorted(rule_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]
    return {**counts, "top_rules": top}



@app.get("/heatmap")
def heatmap(session=Depends(get_db)):
    rows = session.query(ScanRecord).filter(ScanRecord.lat.isnot(None)).all()
    features = []
    for r in rows:
        try:
            fail = (json.loads(r.result_json) or {}).get("summary", {}).get("fail")
        except json.JSONDecodeError:
            fail = None
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [r.lon, r.lat]},
            "properties": {"scan_id": r.scan_id, "verdict": r.verdict,
                           "fail_count": fail,
                           "created_utc": r.created_utc}})
    return {"type": "FeatureCollection", "features": features}


@app.post("/export/edakakhil/{scan_id}")
def export_edakakhil(scan_id: str, session=Depends(get_db)):
    rec = session.get(ScanRecord, scan_id)
    if rec is None:
        raise HTTPException(404, "unknown scan_id")
    if rec.verdict != "VIOLATION":
        raise HTTPException(400, "not a violation — nothing to file")
    if not rec.dossier_sha256:
        raise HTTPException(400, "no dossier attached to this scan")
    return edakakhil_payload(rec.to_export_row())


@app.post("/export/nch1915/{scan_id}")
def export_nch1915(scan_id: str, session=Depends(get_db)):
    rec = session.get(ScanRecord, scan_id)
    if rec is None:
        raise HTTPException(404, "unknown scan_id")
    if rec.verdict != "VIOLATION":
        raise HTTPException(400, "not a violation — nothing to report")
    return nch1915_payload(rec.to_export_row())
