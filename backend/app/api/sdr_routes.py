"""
FastAPI route handlers for RTL-SDR ingestion, historical queries, anomaly feeds,
and report generation.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from ..core.config import get_config
from ..sdr.anomaly_engine import SDRAnomalyEngine
from ..sdr.database import SDRDatabase
from ..sdr.models import (
    SDRAnomalyResponse,
    SDRMeasurementPayload,
    SDRMeasurementResponse,
    SDRStatusResponse,
)
from ..sdr.reports import SDRReportGenerator

router = APIRouter(prefix="/sdr", tags=["sdr"])
config = get_config()
db = SDRDatabase(db_url=config.database_url, storage_dir=config.storage_dir)
anomaly_engine = SDRAnomalyEngine(db)
report_gen = SDRReportGenerator()


async def verify_collector_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    """
    Authenticate incoming collector requests via X-API-Key or Bearer token.
    Never logs or exposes the secret key.
    """
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing collector authentication credentials. Provide X-API-Key or Authorization header.",
        )

    is_valid = await db.validate_api_key(token, config.collector_api_key)
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked collector API key.",
        )

    return token


# ── Ingestion Endpoint ────────────────────────────────────────────────

@router.post("/ingest", status_code=201)
async def ingest_sdr_measurement(
    payload: SDRMeasurementPayload,
    api_key: str = Depends(verify_collector_api_key),
):
    """
    Secure authenticated ingestion endpoint for RTL-SDR physical layer telemetry.
    Validates payload bounds, saves measurement to PostgreSQL (or SQLite local fallback),
    runs signal anomaly detection, deduplicates active events, and tracks recovery.
    """
    # Fetch previous measurement for differential drop detection
    prev_record = await db.get_latest_measurement(payload.device_id)

    # Insert measurement into persistent storage
    saved_record = await db.insert_measurement(payload)

    # Run anomaly evaluation
    anomalies = await anomaly_engine.evaluate(payload, prev_record)

    return {
        "status": "accepted",
        "id": saved_record.id,
        "timestamp": saved_record.timestamp,
        "device_id": saved_record.device_id,
        "mode": saved_record.mode,
        "is_valid": saved_record.is_valid,
        "active_anomalies_count": len(anomalies),
    }


# ── Status & Telemetry Queries ────────────────────────────────────────

@router.get("/latest", response_model=SDRStatusResponse)
async def get_latest_status(device_id: Optional[str] = None):
    """Retrieve the latest SDR telemetry, station health, and active anomalies."""
    latest = await db.get_latest_measurement(device_id)
    active_anomalies = await db.get_active_anomalies(device_id)

    if not latest:
        return SDRStatusResponse(
            status="offline",
            active_anomaly_count=0,
            active_anomalies=[],
            latest_measurement=None,
        )

    # Determine station state
    # Calculate staleness
    status = "active"
    try:
        ts = datetime.fromisoformat(latest.timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_seconds = (now - ts).total_seconds()
        if age_seconds > 45.0:
            status = "offline"
    except Exception:
        pass

    if latest.mode == "demo":
        status = "demo"
    elif not latest.is_valid:
        status = "degraded"
    elif any(a.severity in ("CRITICAL", "ERROR") for a in active_anomalies):
        status = "degraded"

    latest_dict = latest.to_dict()
    measurement_resp = SDRMeasurementResponse(**latest_dict)
    anomaly_resps = [SDRAnomalyResponse(**a.to_dict()) for a in active_anomalies]

    return SDRStatusResponse(
        status=status,
        device_id=latest.device_id,
        device_type=latest.device_type,
        is_synthetic=latest.is_synthetic,
        mode=latest.mode,
        last_seen=latest.timestamp,
        frequency_mhz=round(latest.center_frequency_hz / 1e6, 3),
        sample_rate_msps=round(latest.sample_rate_hz / 1e6, 3),
        relative_power_dbfs=latest.relative_power_dbfs,
        snr_estimate_db=latest.snr_estimate_db,
        active_anomaly_count=len(active_anomalies),
        active_anomalies=anomaly_resps,
        latest_measurement=measurement_resp,
    )


@router.get("/history")
async def get_sdr_history(
    start_time: Optional[str] = Query(None, description="Start ISO 8601 UTC timestamp"),
    end_time: Optional[str] = Query(None, description="End ISO 8601 UTC timestamp"),
    limit: int = Query(100, ge=1, le=2000),
    device_id: Optional[str] = Query(None),
):
    """Query historical telemetry measurements with optional time range filtering."""
    records = await db.get_measurements_history(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        device_id=device_id,
    )
    return {
        "count": len(records),
        "measurements": [r.to_dict() for r in records],
    }


@router.get("/anomalies")
async def get_sdr_anomalies(
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    limit: int = Query(100, ge=1, le=1000),
    device_id: Optional[str] = Query(None),
):
    """Retrieve anomaly events, occurrence counts, and recovery records."""
    records = await db.get_anomalies_history(
        resolved=resolved,
        severity=severity,
        limit=limit,
        device_id=device_id,
    )
    return {
        "count": len(records),
        "anomalies": [a.to_dict() for a in records],
    }


# ── Reports & Exports ─────────────────────────────────────────────────

@router.get("/reports/export")
async def export_sdr_measurements(
    format: str = Query("json", pattern="^(json|csv)$"),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    device_id: Optional[str] = Query(None),
):
    """Export historical SDR telemetry as downloadable JSON or CSV."""
    records = await db.get_measurements_history(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        device_id=device_id,
    )

    now_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if format == "csv":
        csv_data = report_gen.measurements_csv(records)
        return StreamingResponse(
            io.BytesIO(csv_data.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=orbitstream_sdr_telemetry_{now_tag}.csv"},
        )
    else:
        json_data = report_gen.measurements_json(records)
        return StreamingResponse(
            io.BytesIO(json_data.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=orbitstream_sdr_telemetry_{now_tag}.json"},
        )


@router.get("/reports/anomalies")
async def export_sdr_anomalies(
    format: str = Query("json", pattern="^(json|csv)$"),
    resolved: Optional[bool] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=1000),
):
    """Export SDR anomaly events and recovery logs as downloadable JSON or CSV."""
    anomalies = await db.get_anomalies_history(
        resolved=resolved,
        severity=severity,
        limit=limit,
    )

    now_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if format == "csv":
        csv_data = report_gen.anomalies_csv(anomalies)
        return StreamingResponse(
            io.BytesIO(csv_data.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=orbitstream_sdr_anomalies_{now_tag}.csv"},
        )
    else:
        json_data = report_gen.anomalies_json(anomalies)
        return StreamingResponse(
            io.BytesIO(json_data.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=orbitstream_sdr_anomalies_{now_tag}.json"},
        )


@router.get("/reports/pdf", response_class=HTMLResponse)
async def download_sdr_printable_report(device_id: Optional[str] = None):
    """Generate printable HTML/PDF diagnostic report for SDR physical monitoring."""
    status = await get_latest_status(device_id)
    records = await db.get_measurements_history(limit=50, device_id=device_id)
    anomalies = await db.get_anomalies_history(limit=30, device_id=device_id)

    html = report_gen.printable_html_report(status, records, anomalies)
    return HTMLResponse(content=html)


# ── Credential Revocation ─────────────────────────────────────────────

@router.post("/keys/revoke")
async def revoke_collector_key(
    key_string: str = Query(..., description="API key to revoke"),
    admin_key: str = Depends(verify_collector_api_key),
):
    """Revoke a collector credential."""
    success = await db.revoke_api_key(key_string)
    return {"status": "revoked", "key_prefix": key_string[:6]}
