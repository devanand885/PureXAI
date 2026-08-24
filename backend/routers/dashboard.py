"""
routers/dashboard.py — Dashboard read APIs.

Endpoints:
  GET /api/readings/live       — latest sensor reading + device online status
  GET /api/readings/history    — paginated historical readings with filters
  GET /api/status              — current water quality status
  GET /api/sensor-health       — per-sensor health status
  GET /api/stats               — 24-hour summary statistics
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from database import get_db
from models import SensorReading, SensorHealth
from schemas import (
    LiveReadingOut, SensorReadingOut, HistoryOut,
    WaterStatusOut, AllSensorHealthOut, SensorHealthOut, StatsOut,
)
from services.sensor_health import is_device_online
from config import STATUS_UNKNOWN

router = APIRouter(prefix="/api", tags=["Dashboard"])
logger = logging.getLogger("purexai.dashboard")


# ---------------------------------------------------------------------------
# GET /api/readings/live
# ---------------------------------------------------------------------------

@router.get("/readings/live", response_model=LiveReadingOut, summary="Latest sensor reading")
def get_live_reading(db: Session = Depends(get_db)):
    """Returns the most recent sensor reading and device online status."""
    reading = (
        db.query(SensorReading)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )
    online = is_device_online(db)

    last_seen = None
    if reading:
        last_seen = reading.timestamp

    return LiveReadingOut(
        reading=SensorReadingOut.model_validate(reading) if reading else None,
        device_online=online,
        last_seen=last_seen,
        message="Device offline — check ESP32 connection" if not online else "Live",
    )


# ---------------------------------------------------------------------------
# GET /api/readings/history
# ---------------------------------------------------------------------------

@router.get("/readings/history", response_model=HistoryOut, summary="Historical sensor readings")
def get_reading_history(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=500, description="Records per page"),
    start_time: Optional[datetime] = Query(None, description="Filter: start timestamp (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="Filter: end timestamp (ISO 8601)"),
    status: Optional[str] = Query(None, description="Filter by overall_status: Safe/Warning/Unsafe"),
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
):
    """Paginated historical readings with optional time-range, status, and device filters."""
    query = db.query(SensorReading)

    if start_time:
        query = query.filter(SensorReading.timestamp >= start_time)
    if end_time:
        query = query.filter(SensorReading.timestamp <= end_time)
    if status:
        query = query.filter(SensorReading.overall_status == status)
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)

    total = query.count()
    records = (
        query.order_by(SensorReading.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return HistoryOut(
        total=total,
        page=page,
        per_page=per_page,
        data=[SensorReadingOut.model_validate(r) for r in records],
    )


# ---------------------------------------------------------------------------
# GET /api/status
# ---------------------------------------------------------------------------

@router.get("/status", response_model=WaterStatusOut, summary="Current water quality status")
def get_current_status(db: Session = Depends(get_db)):
    """Returns the water quality status derived from the latest reading."""
    reading = (
        db.query(SensorReading)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )
    if not reading:
        return WaterStatusOut(
            overall_status=STATUS_UNKNOWN,
            tds_status=None, turbidity_status=None, temperature_status=None,
            tds_ppm=None, turbidity_ntu=None, temperature_c=None,
            timestamp=None,
            message="No readings available yet.",
        )

    status_messages = {
        "Safe":    "[SAFE] Water quality is SAFE for consumption.",
        "Warning": "[WARNING] Water quality WARNING -- elevated parameters detected.",
        "Unsafe":  "[UNSAFE] Water quality UNSAFE -- do not consume!",
        "Unknown": "[UNKNOWN] Status unknown -- sensor data may be incomplete.",
    }

    return WaterStatusOut(
        overall_status=reading.overall_status,
        tds_status=reading.tds_status,
        turbidity_status=reading.turbidity_status,
        temperature_status=reading.temperature_status,
        tds_ppm=reading.tds_ppm,
        turbidity_ntu=reading.turbidity_ntu,
        temperature_c=reading.temperature_c,
        timestamp=reading.timestamp,
        message=status_messages.get(reading.overall_status, ""),
    )


# ---------------------------------------------------------------------------
# GET /api/sensor-health
# ---------------------------------------------------------------------------

@router.get("/sensor-health", response_model=AllSensorHealthOut, summary="Per-sensor health status")
def get_sensor_health(db: Session = Depends(get_db)):
    """Returns health status for every known sensor."""
    sensors = db.query(SensorHealth).all()
    online = is_device_online(db)

    return AllSensorHealthOut(
        sensors=[SensorHealthOut.model_validate(s) for s in sensors],
        device_online=online,
    )


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsOut, summary="24-hour summary statistics")
def get_stats(db: Session = Depends(get_db)):
    """Returns aggregate statistics for the last 24 hours."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day_ago = now - timedelta(hours=24)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_readings = db.query(func.count(SensorReading.id)).scalar() or 0
    readings_today = (
        db.query(func.count(SensorReading.id))
        .filter(SensorReading.timestamp >= today_start)
        .scalar() or 0
    )

    # 24-hour aggregates
    row = (
        db.query(
            func.avg(SensorReading.tds_ppm),
            func.avg(SensorReading.turbidity_ntu),
            func.avg(SensorReading.temperature_c),
            func.count(SensorReading.id),
            func.sum(case((SensorReading.overall_status == "Safe", 1), else_=0)),
            func.sum(case((SensorReading.overall_status == "Warning", 1), else_=0)),
            func.sum(case((SensorReading.overall_status == "Unsafe", 1), else_=0)),
        )
        .filter(SensorReading.timestamp >= day_ago)
        .first()
    )

    avg_tds, avg_turb, avg_temp, count_24h, safe_n, warn_n, unsafe_n = row

    def pct(n, total):
        if total and total > 0:
            return round((n or 0) / total * 100, 1)
        return None

    return StatsOut(
        total_readings=total_readings,
        readings_today=readings_today,
        avg_tds_24h=round(avg_tds, 2) if avg_tds else None,
        avg_turbidity_24h=round(avg_turb, 2) if avg_turb else None,
        avg_temperature_24h=round(avg_temp, 2) if avg_temp else None,
        safe_pct_24h=pct(safe_n, count_24h),
        warning_pct_24h=pct(warn_n, count_24h),
        unsafe_pct_24h=pct(unsafe_n, count_24h),
    )
