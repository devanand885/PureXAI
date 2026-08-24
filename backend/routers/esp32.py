"""
routers/esp32.py — ESP32 data ingestion endpoint.

POST /api/sensor-data
  • Validates incoming payload (Pydantic)
  • Evaluates thresholds → Safe / Warning / Unsafe
  • Persists SensorReading to DB
  • Updates SensorHealth for each reported sensor
  • Fires threshold alerts if needed
  • Returns acknowledgement to the ESP32
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from models import SensorReading
from schemas import SensorDataIn, SensorDataAck
from services.threshold import evaluate_reading
from services.sensor_health import update_sensor_health
from services.alert_service import create_alert
from config import (
    ALERT_TYPE_THRESHOLD,
    SEVERITY_WARNING,
    SEVERITY_CRITICAL,
    STATUS_WARNING,
    STATUS_UNSAFE,
)

router = APIRouter(prefix="/api", tags=["ESP32"])
logger = logging.getLogger("purexai.esp32")


@router.post("/sensor-data", response_model=SensorDataAck, summary="Receive sensor data from ESP32")
async def receive_sensor_data(
    payload: SensorDataIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Called by the ESP32 every time it has a new sensor reading.
    Validates, evaluates, stores, and triggers alerts as needed.
    """
    # ── 1. Evaluate thresholds ────────────────────────────────────────────
    result = evaluate_reading(
        tds_ppm=payload.tds_ppm,
        turbidity_ntu=payload.turbidity_ntu,
        temperature_c=payload.temperature_c,
    )

    # ── 2. Persist reading ────────────────────────────────────────────────
    reading = SensorReading(
        tds_ppm=payload.tds_ppm,
        turbidity_ntu=payload.turbidity_ntu,
        temperature_c=payload.temperature_c,
        tds_status=result.tds_status,
        turbidity_status=result.turbidity_status,
        temperature_status=result.temperature_status,
        overall_status=result.overall_status,
        device_id=payload.device_id or "esp32-001",
        ip_address=payload.ip_address or request.client.host,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    logger.info(
        f"📥 Reading #{reading.id} | TDS={payload.tds_ppm} | "
        f"Turb={payload.turbidity_ntu} | Temp={payload.temperature_c} | "
        f"Status={result.overall_status}"
    )

    # ── 3. Update sensor health ───────────────────────────────────────────
    if payload.tds_ppm is not None:
        update_sensor_health(db, "tds", value=payload.tds_ppm)
    if payload.turbidity_ntu is not None:
        update_sensor_health(db, "turbidity", value=payload.turbidity_ntu)
    if payload.temperature_c is not None:
        update_sensor_health(db, "temperature", value=payload.temperature_c)

    # ── 4. Fire threshold alerts ──────────────────────────────────────────
    for alert_info in result.alerts_to_fire():
        create_alert(
            db,
            alert_type=alert_info["alert_type"],
            severity=alert_info["severity"],
            sensor_name=alert_info["sensor_name"],
            message=alert_info["message"],
            reading_id=reading.id,
        )

    # ── 5. Acknowledge to ESP32 ───────────────────────────────────────────
    return SensorDataAck(
        success=True,
        reading_id=reading.id,
        overall_status=result.overall_status,
        timestamp=reading.timestamp,
        message=f"Reading stored. Status: {result.overall_status}",
    )


@router.get("/ping", summary="Health-check ping for ESP32")
async def ping():
    """Simple endpoint so the ESP32 can verify server connectivity."""
    return {
        "status": "ok",
        "server_time": datetime.now(timezone.utc).isoformat(),
        "message": "PureXAI backend is alive",
    }
