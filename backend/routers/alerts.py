"""
routers/alerts.py — Alert management endpoints.

Endpoints:
  GET   /api/alerts              — paginated alert history with filters
  GET   /api/alerts/active       — all unresolved alerts
  PATCH /api/alerts/{id}/resolve — mark a single alert resolved
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session

from database import get_db
from models import Alert
from schemas import AlertListOut, AlertOut, AlertResolveIn, AlertResolveOut
from services.alert_service import resolve_alert

router = APIRouter(prefix="/api", tags=["Alerts"])
logger = logging.getLogger("purexai.alerts_router")


# ---------------------------------------------------------------------------
# GET /api/alerts
# ---------------------------------------------------------------------------

@router.get("/alerts", response_model=AlertListOut, summary="Alert history")
def list_alerts(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    device_id: Optional[str] = Query(None, description="Filter by device ID (e.g. esp32-001)"),
    alert_type: Optional[str] = Query(None, description="Filter by alert_type (e.g. THRESHOLD)"),
    severity: Optional[str] = Query(None, description="Filter by severity: INFO/WARNING/CRITICAL"),
    sensor_name: Optional[str] = Query(None, description="Filter by sensor/parameter name"),
    is_resolved: Optional[bool] = Query(None, description="True = show only resolved, False = only active"),
    start_time: Optional[datetime] = Query(None, description="Filter: start timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter: end timestamp"),
):
    """Returns a paginated, filterable list of all alerts."""
    query = db.query(Alert)

    if device_id:
        query = query.filter(Alert.device_id == device_id)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if severity:
        query = query.filter(Alert.severity == severity)
    if sensor_name:
        query = query.filter(Alert.sensor_name == sensor_name)
    if is_resolved is not None:
        query = query.filter(Alert.is_resolved == is_resolved)
    if start_time:
        query = query.filter(Alert.timestamp >= start_time)
    if end_time:
        query = query.filter(Alert.timestamp <= end_time)

    total = query.count()
    records = (
        query.order_by(Alert.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return AlertListOut(
        total=total,
        page=page,
        per_page=per_page,
        data=[AlertOut.model_validate(a) for a in records],
    )


# ---------------------------------------------------------------------------
# GET /api/alerts/active
# ---------------------------------------------------------------------------

@router.get("/alerts/active", response_model=AlertListOut, summary="All active (unresolved) alerts")
def list_active_alerts(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
):
    """Returns all alerts that have not been resolved yet."""
    query = db.query(Alert).filter(Alert.is_resolved == False)   # noqa: E712
    if device_id:
        query = query.filter(Alert.device_id == device_id)
    total = query.count()
    records = (
        query.order_by(Alert.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return AlertListOut(
        total=total, page=page, per_page=per_page,
        data=[AlertOut.model_validate(a) for a in records],
    )


# ---------------------------------------------------------------------------
# PATCH /api/alerts/{id}/resolve
# ---------------------------------------------------------------------------

@router.patch("/alerts/{alert_id}/resolve", response_model=AlertResolveOut, summary="Resolve an alert")
def resolve_alert_endpoint(
    alert_id: int = Path(..., ge=1),
    body: AlertResolveIn = AlertResolveIn(),
    db: Session = Depends(get_db),
):
    """Mark a specific alert as resolved."""
    alert = resolve_alert(db, alert_id, resolved_by=body.resolved_by or "manual")
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert #{alert_id} not found.")
    if not alert.resolved_at:
        raise HTTPException(status_code=400, detail=f"Alert #{alert_id} was already resolved.")

    return AlertResolveOut(
        success=True,
        alert_id=alert.id,
        resolved_at=alert.resolved_at,
    )
