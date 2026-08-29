"""
services/alert_service.py — Alert creation, deduplication, and notification dispatch.

Rules:
  - Deduplication: don't create the same alert_type+sensor_name alert within
    ALERT_COOLDOWN_SECONDS of the last identical unresolved alert.
  - All alerts are logged to the DB and printed to console.
  - Extensible: swap _send_notification() for email/SMS/webhook in future.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config import ALERT_COOLDOWN_SECONDS
from models import Alert

logger = logging.getLogger("purexai.alerts")


# ---------------------------------------------------------------------------
# Internal: deduplication check
# ---------------------------------------------------------------------------

def _is_duplicate(
    db: Session,
    alert_type: str,
    sensor_name: Optional[str],
    device_id: Optional[str] = "esp32-001",
) -> bool:
    """
    Returns True if an identical unresolved alert was created within the cooldown window.
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=ALERT_COOLDOWN_SECONDS)
    query = (
        db.query(Alert)
        .filter(
            Alert.alert_type == alert_type,
            Alert.is_resolved == False,          # noqa: E712
            Alert.timestamp >= cutoff,
        )
    )
    if device_id:
        query = query.filter(Alert.device_id == device_id)
    if sensor_name:
        query = query.filter(Alert.sensor_name == sensor_name)
    return query.first() is not None


# ---------------------------------------------------------------------------
# Internal: console + extensible notification
# ---------------------------------------------------------------------------

def _send_notification(alert: Alert):
    """Send alert notification. Currently logs to console."""
    icon = {"INFO": "[INFO]", "WARNING": "[WARNING]", "CRITICAL": "[CRITICAL]"}.get(alert.severity, "[ALERT]")
    logger.warning(
        f"{icon}  [{alert.severity}] {alert.alert_type} | "
        f"Device: {alert.device_id or 'N/A'} | Sensor: {alert.sensor_name or 'N/A'} | {alert.message}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_alert(
    db: Session,
    alert_type: str,
    severity: str,
    message: str,
    sensor_name: Optional[str] = None,
    device_id: Optional[str] = "esp32-001",
    value: Optional[float] = None,
    threshold: Optional[float] = None,
    reading_id: Optional[int] = None,
    skip_dedup: bool = False,
) -> Optional[Alert]:
    """
    Create and persist an alert.

    Returns the created Alert, or None if deduplicated.
    """
    if not skip_dedup and _is_duplicate(db, alert_type, sensor_name, device_id=device_id):
        logger.debug(
            f"Dedup: suppressed {alert_type}/{sensor_name} alert for {device_id} (within cooldown)"
        )
        return None

    alert = Alert(
        device_id=device_id or "esp32-001",
        alert_type=alert_type,
        severity=severity,
        sensor_name=sensor_name,
        message=message,
        value=value,
        threshold=threshold,
        reading_id=reading_id,
        is_resolved=False,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    _send_notification(alert)
    return alert


def resolve_alert(
    db: Session,
    alert_id: int,
    resolved_by: str = "auto",
) -> Optional[Alert]:
    """Mark an alert as resolved."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert or alert.is_resolved:
        return alert
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    alert.resolved_by = resolved_by
    db.commit()
    db.refresh(alert)
    return alert


def auto_resolve_sensor_alerts(
    db: Session,
    sensor_name: str,
    alert_type: str,
    device_id: Optional[str] = "esp32-001",
) -> int:
    """
    Auto-resolve all open alerts for a sensor+type (e.g., when sensor comes back online).
    Returns number of alerts resolved.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = (
        db.query(Alert)
        .filter(
            Alert.sensor_name == sensor_name,
            Alert.alert_type == alert_type,
            Alert.is_resolved == False,          # noqa: E712
        )
    )
    if device_id:
        query = query.filter(Alert.device_id == device_id)
    alerts = query.all()
    for a in alerts:
        a.is_resolved = True
        a.resolved_at = now
        a.resolved_by = "auto"
    db.commit()
    return len(alerts)
