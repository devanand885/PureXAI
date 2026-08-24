"""
services/disconnection.py — ESP32 / Wi-Fi disconnection handler.

Monitors device-level connectivity. If no data has arrived from the device
within the offline threshold, fires a DEVICE_OFFLINE alert.
Runs as a background APScheduler job.
"""

import logging
from datetime import datetime, timezone, timedelta

from config import (
    SENSOR_OFFLINE_THRESHOLD_SECONDS,
    ALERT_TYPE_DEVICE_OFFLINE,
    ALERT_TYPE_SENSOR_RECOVERED,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
)
from database import SessionLocal
from models import SensorHealth
from services.alert_service import create_alert, auto_resolve_sensor_alerts

logger = logging.getLogger("purexai.disconnection")

# Track last-known device state so we only alert on state changes
_device_was_online: bool = True


def run_disconnection_check():
    """
    Background job — called by APScheduler.

    Checks if the ESP32 device is still sending data.
    Fires DEVICE_OFFLINE alert when first disconnect is detected.
    Fires SENSOR_RECOVERED alert when device reconnects.
    """
    global _device_was_online
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            seconds=SENSOR_OFFLINE_THRESHOLD_SECONDS
        )

        # Consider device online if ANY sensor reported recently
        recent = (
            db.query(SensorHealth)
            .filter(SensorHealth.last_seen >= cutoff)
            .first()
        )
        device_online = recent is not None

        if not device_online and _device_was_online:
            # Device just went offline → fire DEVICE_OFFLINE alert
            logger.error(
                f"🔴 ESP32 device OFFLINE — no data received for "
                f">{SENSOR_OFFLINE_THRESHOLD_SECONDS}s"
            )
            create_alert(
                db,
                alert_type=ALERT_TYPE_DEVICE_OFFLINE,
                severity=SEVERITY_CRITICAL,
                sensor_name="esp32",
                message=(
                    f"ESP32 device has gone offline. "
                    f"No sensor data received for >{SENSOR_OFFLINE_THRESHOLD_SECONDS} seconds. "
                    f"Check power supply, Wi-Fi connection, and firmware."
                ),
            )
            _device_was_online = False

        elif device_online and not _device_was_online:
            # Device just came back online → auto-resolve and log recovery
            logger.info("🟢 ESP32 device back ONLINE")
            auto_resolve_sensor_alerts(db, "esp32", ALERT_TYPE_DEVICE_OFFLINE)
            create_alert(
                db,
                alert_type=ALERT_TYPE_SENSOR_RECOVERED,
                severity=SEVERITY_INFO,
                sensor_name="esp32",
                message="ESP32 device has reconnected and is sending data.",
                skip_dedup=True,
            )
            _device_was_online = True

    except Exception as exc:
        logger.error(f"Disconnection check error: {exc}", exc_info=True)
    finally:
        db.close()
