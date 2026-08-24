"""
config.py — PureXAI Backend Configuration
Central place for all thresholds, constants, and settings.
"""

from pydantic_settings import BaseSettings
from typing import Dict, Any


# ---------------------------------------------------------------------------
# Water-Quality Thresholds
# ---------------------------------------------------------------------------

class TDSThreshold:
    SAFE_MAX: float = 300.0       # ppm — below this is Safe
    WARNING_MAX: float = 600.0    # ppm — 300–600 is Warning, above is Unsafe


class TurbidityThreshold:
    SAFE_MAX: float = 1.0         # NTU — below this is Safe
    WARNING_MAX: float = 4.0      # NTU — 1–4 is Warning, above is Unsafe


class TemperatureThreshold:
    SAFE_MIN: float = 10.0        # °C
    SAFE_MAX: float = 25.0        # °C — 10–25 is Safe
    WARNING_MIN: float = 5.0      # °C — 5–10 is Warning-cold
    WARNING_MAX: float = 35.0     # °C — 25–35 is Warning-hot
    # Below WARNING_MIN or above WARNING_MAX → Unsafe


# ---------------------------------------------------------------------------
# Sensor Health
# ---------------------------------------------------------------------------

SENSOR_OFFLINE_THRESHOLD_SECONDS: int = 30   # seconds of silence → OFFLINE
HEALTH_CHECK_INTERVAL_SECONDS: int = 15      # how often background task runs

# Known sensor IDs — can be extended
KNOWN_SENSORS = ["tds", "turbidity", "temperature", "oled"]


# ---------------------------------------------------------------------------
# Alert Deduplication
# ---------------------------------------------------------------------------

ALERT_COOLDOWN_SECONDS: int = 60   # minimum gap between identical alerts


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_URL: str = "sqlite:///./data/purexai.db"


# ---------------------------------------------------------------------------
# App Settings (from .env or environment variables)
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    APP_NAME: str = "PureXAI Water Quality Monitor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    DATABASE_URL: str = DATABASE_URL
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Optional notification settings (extensible)
    NOTIFY_EMAIL: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


# ---------------------------------------------------------------------------
# Status Labels
# ---------------------------------------------------------------------------

STATUS_SAFE = "Safe"
STATUS_WARNING = "Warning"
STATUS_UNSAFE = "Unsafe"
STATUS_UNKNOWN = "Unknown"

# Alert types
ALERT_TYPE_THRESHOLD = "THRESHOLD"
ALERT_TYPE_SENSOR_OFFLINE = "SENSOR_OFFLINE"
ALERT_TYPE_DEVICE_OFFLINE = "DEVICE_OFFLINE"
ALERT_TYPE_SENSOR_RECOVERED = "SENSOR_RECOVERED"

# Severity levels
SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_CRITICAL = "CRITICAL"
