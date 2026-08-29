"""
services/threshold.py — Water quality threshold evaluation.

Evaluates each sensor reading against configured thresholds and returns
a status of Safe, Warning, or Unsafe with a human-readable reason.
"""

from typing import Optional, Tuple

from config import (
    TDSThreshold, TurbidityThreshold, TemperatureThreshold,
    STATUS_SAFE, STATUS_WARNING, STATUS_UNSAFE, STATUS_UNKNOWN,
)


# ---------------------------------------------------------------------------
# Individual parameter evaluators
# ---------------------------------------------------------------------------

def evaluate_tds(tds_ppm: Optional[float]) -> Tuple[str, str]:
    """
    Returns (status, reason).
    """
    if tds_ppm is None:
        return STATUS_UNKNOWN, "TDS sensor not reporting"
    if tds_ppm < TDSThreshold.SAFE_MAX:
        return STATUS_SAFE, f"TDS {tds_ppm:.1f} ppm — within safe range (<{TDSThreshold.SAFE_MAX} ppm)"
    if tds_ppm <= TDSThreshold.WARNING_MAX:
        return STATUS_WARNING, f"TDS {tds_ppm:.1f} ppm — elevated ({TDSThreshold.SAFE_MAX}–{TDSThreshold.WARNING_MAX} ppm)"
    return STATUS_UNSAFE, f"TDS {tds_ppm:.1f} ppm — dangerously high (>{TDSThreshold.WARNING_MAX} ppm)"


def evaluate_turbidity(turbidity_ntu: Optional[float]) -> Tuple[str, str]:
    """
    Returns (status, reason).
    """
    if turbidity_ntu is None:
        return STATUS_UNKNOWN, "Turbidity sensor not reporting"
    if turbidity_ntu < TurbidityThreshold.SAFE_MAX:
        return STATUS_SAFE, f"Turbidity {turbidity_ntu:.2f} NTU — clear water (<{TurbidityThreshold.SAFE_MAX} NTU)"
    if turbidity_ntu <= TurbidityThreshold.WARNING_MAX:
        return STATUS_WARNING, f"Turbidity {turbidity_ntu:.2f} NTU — slightly cloudy ({TurbidityThreshold.SAFE_MAX}–{TurbidityThreshold.WARNING_MAX} NTU)"
    return STATUS_UNSAFE, f"Turbidity {turbidity_ntu:.2f} NTU — very cloudy/unsafe (>{TurbidityThreshold.WARNING_MAX} NTU)"


def evaluate_temperature(temperature_c: Optional[float]) -> Tuple[str, str]:
    """
    Returns (status, reason).
    """
    if temperature_c is None:
        return STATUS_UNKNOWN, "Temperature sensor not reporting"
    t = temperature_c
    T = TemperatureThreshold
    if T.SAFE_MIN <= t <= T.SAFE_MAX:
        return STATUS_SAFE, f"Temperature {t:.1f}°C — optimal range ({T.SAFE_MIN}–{T.SAFE_MAX}°C)"
    if T.WARNING_MIN <= t < T.SAFE_MIN:
        return STATUS_WARNING, f"Temperature {t:.1f}°C — slightly cold ({T.WARNING_MIN}–{T.SAFE_MIN}°C)"
    if T.SAFE_MAX < t <= T.WARNING_MAX:
        return STATUS_WARNING, f"Temperature {t:.1f}°C — slightly warm ({T.SAFE_MAX}–{T.WARNING_MAX}°C)"
    if t > T.WARNING_MAX:
        return STATUS_UNSAFE, f"Temperature {t:.1f}°C — dangerously hot (>{T.WARNING_MAX}°C)"
    # t < WARNING_MIN
    return STATUS_UNSAFE, f"Temperature {t:.1f}°C — dangerously cold (<{T.WARNING_MIN}°C)"


# ---------------------------------------------------------------------------
# Overall status aggregator
# ---------------------------------------------------------------------------

_PRIORITY = {STATUS_UNSAFE: 3, STATUS_WARNING: 2, STATUS_SAFE: 1, STATUS_UNKNOWN: 0}


def compute_overall_status(
    tds_status: str,
    turbidity_status: str,
    temperature_status: str,
) -> str:
    """
    Returns the worst status across all three parameters.
    Priority: Unsafe > Warning > Safe > Unknown
    """
    statuses = [tds_status, turbidity_status, temperature_status]
    return max(statuses, key=lambda s: _PRIORITY.get(s, 0))


# ---------------------------------------------------------------------------
# Full reading evaluation — convenience wrapper
# ---------------------------------------------------------------------------

class ThresholdResult:
    def __init__(
        self,
        tds_ppm: Optional[float],
        turbidity_ntu: Optional[float],
        temperature_c: Optional[float],
        tds_status: str,       tds_reason: str,
        turbidity_status: str, turbidity_reason: str,
        temperature_status: str, temperature_reason: str,
        overall_status: str,
    ):
        self.tds_ppm             = tds_ppm
        self.turbidity_ntu       = turbidity_ntu
        self.temperature_c       = temperature_c
        self.tds_status          = tds_status
        self.tds_reason          = tds_reason
        self.turbidity_status    = turbidity_status
        self.turbidity_reason    = turbidity_reason
        self.temperature_status  = temperature_status
        self.temperature_reason  = temperature_reason
        self.overall_status      = overall_status

    @property
    def is_safe(self) -> bool:
        return self.overall_status == STATUS_SAFE

    @property
    def has_alert(self) -> bool:
        return self.overall_status in (STATUS_WARNING, STATUS_UNSAFE)

    def alerts_to_fire(self) -> list[dict]:
        """Returns list of alert dicts with parameter, value, and threshold for any non-safe parameters."""
        alerts = []
        checks = [
            ("tds",         self.tds_status,         self.tds_reason,         self.tds_ppm,        TDSThreshold.SAFE_MAX if self.tds_status == STATUS_WARNING else TDSThreshold.WARNING_MAX),
            ("turbidity",   self.turbidity_status,   self.turbidity_reason,   self.turbidity_ntu,  TurbidityThreshold.SAFE_MAX if self.turbidity_status == STATUS_WARNING else TurbidityThreshold.WARNING_MAX),
            ("temperature", self.temperature_status, self.temperature_reason, self.temperature_c, TemperatureThreshold.SAFE_MAX if (self.temperature_c is not None and self.temperature_c > TemperatureThreshold.SAFE_MAX) else TemperatureThreshold.SAFE_MIN),
        ]
        from config import SEVERITY_WARNING, SEVERITY_CRITICAL, ALERT_TYPE_THRESHOLD
        for sensor, status, reason, val, thresh in checks:
            if status == STATUS_WARNING:
                alerts.append({
                    "alert_type":  ALERT_TYPE_THRESHOLD,
                    "severity":    SEVERITY_WARNING,
                    "sensor_name": sensor,
                    "message":     reason,
                    "value":       val,
                    "threshold":   thresh,
                })
            elif status == STATUS_UNSAFE:
                alerts.append({
                    "alert_type":  ALERT_TYPE_THRESHOLD,
                    "severity":    SEVERITY_CRITICAL,
                    "sensor_name": sensor,
                    "message":     reason,
                    "value":       val,
                    "threshold":   thresh,
                })
        return alerts


def evaluate_reading(
    tds_ppm: Optional[float],
    turbidity_ntu: Optional[float],
    temperature_c: Optional[float],
) -> ThresholdResult:
    """Full threshold evaluation for a single reading."""
    tds_st,   tds_r   = evaluate_tds(tds_ppm)
    turb_st,  turb_r  = evaluate_turbidity(turbidity_ntu)
    temp_st,  temp_r  = evaluate_temperature(temperature_c)
    overall           = compute_overall_status(tds_st, turb_st, temp_st)

    return ThresholdResult(
        tds_ppm=tds_ppm,
        turbidity_ntu=turbidity_ntu,
        temperature_c=temperature_c,
        tds_status=tds_st,           tds_reason=tds_r,
        turbidity_status=turb_st,    turbidity_reason=turb_r,
        temperature_status=temp_st,  temperature_reason=temp_r,
        overall_status=overall,
    )
