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
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from netra_core.sync.exporters import edakakhil_payload, nch1915_payload

from . import db
from .models import ScanRecord

app = FastAPI(title="NETRA institutional gateway", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
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
def ingest(envelope: dict, session=Depends(get_db)):
    err = _validate(envelope)
    if err:
        raise HTTPException(status_code=err[0], detail=err[1])
    if session.get(ScanRecord, envelope["scan_id"]) is not None:
        return {"accepted": True, "duplicate": True,
                "scan_id": envelope["scan_id"]}
    gps = ((envelope.get("result") or {}).get("meta") or {}).get("gps") or {}
    lat, lon = gps.get("lat"), gps.get("lon")
    rec = ScanRecord(
        scan_id=envelope["scan_id"], verdict=envelope["verdict"],
        created_utc=envelope.get("created_utc"), received_utc=_now(),
        image_sha256=envelope.get("image_sha256"),
        dossier_sha256=envelope.get("dossier_sha256"),
        signature=envelope.get("signature"),
        cert_pem=envelope.get("cert_pem"),
        sig_verified=bool(envelope.get("sig_verified")),
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
    rows = session.query(ScanRecord).all()
    counts = {"total": len(rows), "violation": 0, "pass": 0, "signed": 0,
              "located": 0}
    rule_counts: dict = {}
    for r in rows:
        if r.verdict == "VIOLATION":
            counts["violation"] += 1
        else:
            counts["pass"] += 1
        if r.sig_status == "signed":
            counts["signed"] += 1
        if r.lat is not None:
            counts["located"] += 1
        try:
            for c in (json.loads(r.result_json) or {}).get("checks") or []:
                if c.get("status") == "FAIL":
                    rule_counts[c.get("rule")] = \
                        rule_counts.get(c.get("rule"), 0) + 1
        except json.JSONDecodeError:
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
