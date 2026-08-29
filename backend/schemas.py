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
    All sensor fields can be provided or omitted if sensor is unavailable.
    Invalid/NaN/negative numbers are strictly rejected with 422.
    """
    tds_ppm:        Optional[float] = Field(None, ge=0.0, le=5000.0, description="TDS in ppm (0–5000)")
    turbidity_ntu:  Optional[float] = Field(None, ge=0.0, le=3000.0, description="Turbidity in NTU (0–3000)")
    temperature_c:  Optional[float] = Field(None, ge=-10.0, le=100.0, description="Temperature in °C (-10–100)")
    device_id:      Optional[str]   = Field("esp32-001", min_length=1, max_length=64, description="ESP32 hardware device identifier")
    ip_address:     Optional[str]   = Field(None, max_length=45, description="Client LAN/WAN IP address")

    @field_validator("tds_ppm", "turbidity_ntu", "temperature_c", mode="before")
    @classmethod
    def reject_nan_and_inf(cls, v):
        if v is not None:
            try:
                fv = float(v)
                if fv != fv or fv == float("inf") or fv == float("-inf"):
                    raise ValueError("Sensor reading cannot be NaN or Infinite")
                return fv
            except (TypeError, ValueError) as err:
                raise ValueError(f"Invalid sensor numeric value: {v}") from err
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
    id:                 int
    timestamp:          datetime
    tds_ppm:            Optional[float]
    turbidity_ntu:      Optional[float]
    temperature_c:      Optional[float]
    tds_status:         Optional[str]
    turbidity_status:   Optional[str]
    temperature_status: Optional[str]
    overall_status:     str
    device_id:          Optional[str]


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
    total_readings:       int
    readings_today:       int
    avg_tds_24h:          Optional[float]
    avg_turbidity_24h:    Optional[float]
    avg_temperature_24h:  Optional[float]
    safe_count_24h:       int = 0
    warning_count_24h:    int = 0
    unsafe_count_24h:     int = 0
    safe_pct_24h:         Optional[float]
    warning_pct_24h:      Optional[float]
    unsafe_pct_24h:       Optional[float]
    active_alerts_count:  int = 0
    device_status:        str = "OFFLINE"


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
    device_id:   str
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
    device_id:   Optional[str]
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
