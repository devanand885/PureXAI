"""
schemas.py — Pydantic schemas for request/response validation.
Keeps API contracts clearly defined and separate from ORM models.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------
class OrmBase(BaseModel):
    model_config = {"from_attributes": True}


# ===========================================================================
# ESP32 → Backend (inbound)
# ===========================================================================

class SensorDataIn(BaseModel):
    """
    Payload sent by the ESP32 via POST /api/sensor-data.
    All sensor fields are optional so a partially-functioning device
    can still submit data.
    """
    tds_ppm:        Optional[float] = Field(None, ge=0, le=5000,  description="TDS in ppm")
    turbidity_ntu:  Optional[float] = Field(None, ge=0, le=3000,  description="Turbidity in NTU")
    temperature_c:  Optional[float] = Field(None, ge=-10, le=100, description="Temperature in °C")
    device_id:      Optional[str]   = Field("esp32-001", max_length=64)
    ip_address:     Optional[str]   = Field(None, max_length=45)

    @field_validator("tds_ppm", "turbidity_ntu", "temperature_c", mode="before")
    @classmethod
    def reject_negative_nan(cls, v):
        if v is not None and v != v:   # NaN check
            return None
        return v


class SensorDataAck(BaseModel):
    """Response returned to ESP32 after successful ingestion."""
    success:        bool
    reading_id:     int
    overall_status: str
    timestamp:      datetime
    message:        str = "Data received"


# ===========================================================================
# SensorReading (outbound)
# ===========================================================================

class SensorReadingOut(OrmBase):
    id:               int
    timestamp:        datetime
    tds_ppm:          Optional[float]
    turbidity_ntu:    Optional[float]
    temperature_c:    Optional[float]
    tds_status:       Optional[str]
    turbidity_status: Optional[str]
    temperature_status: Optional[str]
    overall_status:   str
    device_id:        Optional[str]


class LiveReadingOut(BaseModel):
    """Latest reading with extra context for the dashboard."""
    reading:        Optional[SensorReadingOut]
    device_online:  bool
    last_seen:      Optional[datetime]
    message:        str = ""


class HistoryOut(BaseModel):
    total:    int
    page:     int
    per_page: int
    data:     List[SensorReadingOut]


class StatsOut(BaseModel):
    total_readings:   int
    readings_today:   int
    avg_tds_24h:      Optional[float]
    avg_turbidity_24h: Optional[float]
    avg_temperature_24h: Optional[float]
    safe_pct_24h:     Optional[float]
    warning_pct_24h:  Optional[float]
    unsafe_pct_24h:   Optional[float]


# ===========================================================================
# Status
# ===========================================================================

class WaterStatusOut(BaseModel):
    overall_status:     str
    tds_status:         Optional[str]
    turbidity_status:   Optional[str]
    temperature_status: Optional[str]
    tds_ppm:            Optional[float]
    turbidity_ntu:      Optional[float]
    temperature_c:      Optional[float]
    timestamp:          Optional[datetime]
    message:            str


# ===========================================================================
# SensorHealth
# ===========================================================================

class SensorHealthOut(OrmBase):
    id:          int
    sensor_name: str
    status:      str
    last_seen:   Optional[datetime]
    last_value:  Optional[float]
    error_count: int
    updated_at:  Optional[datetime]


class AllSensorHealthOut(BaseModel):
    sensors:       List[SensorHealthOut]
    device_online: bool


# ===========================================================================
# Alerts
# ===========================================================================

class AlertOut(OrmBase):
    id:          int
    timestamp:   datetime
    alert_type:  str
    severity:    str
    sensor_name: Optional[str]
    message:     str
    value:       Optional[float]
    threshold:   Optional[float]
    is_resolved: bool
    resolved_at: Optional[datetime]
    reading_id:  Optional[int]


class AlertListOut(BaseModel):
    total:    int
    page:     int
    per_page: int
    data:     List[AlertOut]


class AlertResolveIn(BaseModel):
    resolved_by: Optional[str] = "manual"


class AlertResolveOut(BaseModel):
    success:     bool
    alert_id:    int
    resolved_at: datetime
