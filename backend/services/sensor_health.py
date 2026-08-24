"""
services/sensor_health.py — Per-sensor health monitoring.

Runs as a background APScheduler job every HEALTH_CHECK_INTERVAL_SECONDS.
Marks any sensor OFFLINE if it hasn't been updated within SENSOR_OFFLINE_THRESHOLD_SECONDS.
On recovery, auto-resolves SENSOR_OFFLINE alerts.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config import (
    SENSOR_OFFLINE_THRESHOLD_SECONDS,
    KNOWN_SENSORS,
    ALERT_TYPE_SENSOR_OFFLINE,
    ALERT_TYPE_SENSOR_RECOVERED,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)
from database import SessionLocal
from models import SensorHealth
from services.alert_service import (
    create_alert,
    auto_resolve_sensor_alerts,
)

logger = logging.getLogger("purexai.sensor_health")


# ---------------------------------------------------------------------------
# Upsert sensor health record
# ---------------------------------------------------------------------------

def update_sensor_health(
    db: Session,
    sensor_name: str,
    value: Optional[float] = None,
    status: str = "ONLINE",
) -> SensorHealth:
    """Called each time fresh data arrives for a sensor."""
    health = db.query(SensorHealth).filter(SensorHealth.sensor_name == sensor_name).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if health is None:
        health = SensorHealth(sensor_name=sensor_name)
        db.add(health)

    prev_status = health.status
    health.status     = status
    health.last_seen  = now
    health.last_value = value
    health.updated_at = now

    # If we're recovering from OFFLINE → resolve outstanding alerts
    if prev_status == "OFFLINE" and status == "ONLINE":
        health.error_count = 0
        db.commit()
        auto_resolve_sensor_alerts(db, sensor_name, ALERT_TYPE_SENSOR_OFFLINE)
        create_alert(
            db,
            alert_type=ALERT_TYPE_SENSOR_RECOVERED,
            severity=SEVERITY_INFO,
            sensor_name=sensor_name,
            message=f"Sensor '{sensor_name}' has come back online.",
            skip_dedup=True,
        )
        logger.info(f"✅ Sensor '{sensor_name}' recovered (was OFFLINE)")
    else:
        db.commit()

    return health


def mark_sensor_offline(db: Session, sensor_name: str):
    """Mark sensor as OFFLINE and fire an alert."""
    health = db.query(SensorHealth).filter(SensorHealth.sensor_name == sensor_name).first()
    if health is None:
        return   # sensor never registered — nothing to do

    if health.status == "OFFLINE":
        return   # already offline, dedup handles alert suppression

    logger.warning(f"⚠️  Sensor '{sensor_name}' going OFFLINE (no data for >{SENSOR_OFFLINE_THRESHOLD_SECONDS}s)")
    health.status = "OFFLINE"
    health.error_count = (health.error_count or 0) + 1
    db.commit()

    create_alert(
        db,
        alert_type=ALERT_TYPE_SENSOR_OFFLINE,
        severity=SEVERITY_WARNING,
        sensor_name=sensor_name,
        message=(
            f"Sensor '{sensor_name}' has not reported data for more than "
            f"{SENSOR_OFFLINE_THRESHOLD_SECONDS} seconds."
        ),
    )


# ---------------------------------------------------------------------------
# Background health check — called by APScheduler
# ---------------------------------------------------------------------------

def run_sensor_health_check():
    """
    Periodic background job.
    Checks every known sensor's last_seen and marks it OFFLINE if stale.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            seconds=SENSOR_OFFLINE_THRESHOLD_SECONDS
        )
        for sensor_name in KNOWN_SENSORS:
            health = (
                db.query(SensorHealth)
                .filter(SensorHealth.sensor_name == sensor_name)
                .first()
            )
            if health is None:
                continue   # sensor never registered — skip
            if health.last_seen is None or health.last_seen < cutoff:
                mark_sensor_offline(db, sensor_name)
    except Exception as exc:
        logger.error(f"Sensor health check error: {exc}", exc_info=True)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Device-level online check (used by dashboard API)
# ---------------------------------------------------------------------------

def is_device_online(db: Session) -> bool:
    """
    Returns True if ANY sensor has reported in the last SENSOR_OFFLINE_THRESHOLD_SECONDS.
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        seconds=SENSOR_OFFLINE_THRESHOLD_SECONDS
    )
    return (
        db.query(SensorHealth)
        .filter(SensorHealth.last_seen >= cutoff)
        .first()
    ) is not None
