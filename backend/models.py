"""
models.py — SQLAlchemy ORM models.

Tables:
  - SensorReading   : every data point from the ESP32
  - SensorHealth    : current health/online status per sensor
  - Alert           : threshold and health alert log
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Float, String, Boolean,
    DateTime, Text, ForeignKey, Index,
)
from sqlalchemy.orm import relationship

from database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# SensorReading
# ---------------------------------------------------------------------------
class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id              = Column(Integer, primary_key=True, index=True)
    timestamp       = Column(DateTime, default=utcnow, nullable=False, index=True)

    # Raw sensor values
    tds_ppm         = Column(Float, nullable=True)    # Total Dissolved Solids
    turbidity_ntu   = Column(Float, nullable=True)    # Turbidity
    temperature_c   = Column(Float, nullable=True)    # Temperature (DS18B20)

    # Derived status for each parameter
    tds_status      = Column(String(16), nullable=True)    # Safe / Warning / Unsafe
    turbidity_status= Column(String(16), nullable=True)
    temperature_status = Column(String(16), nullable=True)

    # Overall water quality status
    overall_status  = Column(String(16), nullable=False, default="Unknown")

    # Device metadata
    device_id       = Column(String(64), nullable=True, default="esp32-001")
    ip_address      = Column(String(45), nullable=True)   # IPv4/IPv6

    # Relationships
    alerts = relationship("Alert", back_populates="reading", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sensor_readings_device_ts", "device_id", "timestamp"),
    )

    def __repr__(self):
        return (
            f"<SensorReading id={self.id} ts={self.timestamp} "
            f"tds={self.tds_ppm} turb={self.turbidity_ntu} "
            f"temp={self.temperature_c} status={self.overall_status}>"
        )


# ---------------------------------------------------------------------------
# SensorHealth
# ---------------------------------------------------------------------------
class SensorHealth(Base):
    __tablename__ = "sensor_health"

    id          = Column(Integer, primary_key=True, index=True)
    sensor_name = Column(String(64), unique=True, nullable=False, index=True)
    status      = Column(String(16), nullable=False, default="UNKNOWN")
    # ONLINE | OFFLINE | DEGRADED | UNKNOWN

    last_seen   = Column(DateTime, nullable=True)
    last_value  = Column(Float, nullable=True)
    error_count = Column(Integer, default=0)
    updated_at  = Column(DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self):
        return f"<SensorHealth {self.sensor_name}={self.status} last_seen={self.last_seen}>"


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------
class Alert(Base):
    __tablename__ = "alerts"

    id          = Column(Integer, primary_key=True, index=True)
    timestamp   = Column(DateTime, default=utcnow, nullable=False, index=True)

    alert_type  = Column(String(32), nullable=False)
    # THRESHOLD | SENSOR_OFFLINE | DEVICE_OFFLINE | SENSOR_RECOVERED

    severity    = Column(String(16), nullable=False, default="WARNING")
    # INFO | WARNING | CRITICAL

    sensor_name = Column(String(64), nullable=True)   # which sensor triggered
    message     = Column(Text, nullable=False)
    value       = Column(Float, nullable=True)         # offending value if any
    threshold   = Column(Float, nullable=True)         # threshold that was breached

    is_resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(64), nullable=True)   # "auto" or username

    # FK to the reading that caused this alert (optional)
    reading_id  = Column(Integer, ForeignKey("sensor_readings.id", ondelete="SET NULL"), nullable=True)
    reading     = relationship("SensorReading", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_type_ts", "alert_type", "timestamp"),
        Index("ix_alerts_resolved", "is_resolved"),
    )

    def __repr__(self):
        return (
            f"<Alert id={self.id} type={self.alert_type} "
            f"severity={self.severity} resolved={self.is_resolved}>"
        )
