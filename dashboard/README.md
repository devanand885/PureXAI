# PureXAI — Streamlit Dashboard Integration Guide (Jai Surya)

This guide documents how the **Streamlit Dashboard** communicates with the **FastAPI Backend**.

> **CRITICAL ARCHITECTURE RULE**:
> The Streamlit dashboard must **NEVER** directly access the SQLite database file or import SQLAlchemy models.
> All data (live readings, history, sensor health, statistics, alerts) must be retrieved exclusively via **HTTP REST APIs**.

---

## 1. Backend Base URL Configuration

In your Streamlit application:
```python
import os
import requests

# Base URL configured via environment variable or default to localhost
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
```

---

## 2. API Endpoints Reference for Dashboard

### A. Live Sensor Readings (`GET /api/readings/live`)
Returns the latest available sensor reading, individual parameter statuses, overall status, and device online flag.

```python
response = requests.get(f"{BACKEND_URL}/api/readings/live")
data = response.json()

# Response structure:
# {
#   "reading": {
#     "id": 42,
#     "timestamp": "2026-08-29T12:00:00",
#     "tds_ppm": 245.3,
#     "turbidity_ntu": 0.72,
#     "temperature_c": 22.1,
#     "tds_status": "Safe",
#     "turbidity_status": "Safe",
#     "temperature_status": "Safe",
#     "overall_status": "Safe",
#     "device_id": "esp32-001"
#   },
#   "device_online": true,
#   "last_seen": "2026-08-29T12:00:00",
#   "message": "Live"
# }
```

---

### B. Current Water-Quality Status (`GET /api/status`)
Returns summary status for quick indicator badges (Safe / Warning / Unsafe).

```python
response = requests.get(f"{BACKEND_URL}/api/status")
status_data = response.json()

# {
#   "overall_status": "Safe",
#   "tds_status": "Safe",
#   "turbidity_status": "Safe",
#   "temperature_status": "Safe",
#   "tds_ppm": 245.3,
#   "turbidity_ntu": 0.72,
#   "temperature_c": 22.1,
#   "timestamp": "2026-08-29T12:00:00",
#   "message": "[SAFE] Water quality is SAFE for consumption."
# }
```

---

### C. 24-Hour Statistics (`GET /api/stats`)
Returns aggregated metrics for metrics cards and summary widgets.

```python
response = requests.get(f"{BACKEND_URL}/api/stats")
stats = response.json()

# {
#   "total_readings": 1250,
#   "readings_today": 340,
#   "avg_tds_24h": 220.4,
#   "avg_turbidity_24h": 0.65,
#   "avg_temperature_24h": 21.8,
#   "safe_count_24h": 1200,
#   "warning_count_24h": 40,
#   "unsafe_count_24h": 10,
#   "safe_pct_24h": 96.0,
#   "warning_pct_24h": 3.2,
#   "unsafe_pct_24h": 0.8,
#   "active_alerts_count": 0,
#   "device_status": "ONLINE"
# }
```

---

### D. Historical Readings (`GET /api/readings/history`)
Use this for time-series charts (Plotly / Altair / Streamlit line charts).

**Query Parameters**:
- `page` *(int, default: 1)*
- `per_page` *(int, default: 50, max: 500)*
- `start_time` *(ISO datetime string, optional)*: e.g. `2026-08-29T00:00:00`
- `end_time` *(ISO datetime string, optional)*: e.g. `2026-08-29T23:59:59`
- `status` *(string, optional)*: `"Safe"`, `"Warning"`, or `"Unsafe"`
- `device_id` *(string, optional)*: `"esp32-001"`

```python
params = {
    "per_page": 200,
    "start_time": "2026-08-28T00:00:00",
    "end_time": "2026-08-29T23:59:59"
}
response = requests.get(f"{BACKEND_URL}/api/readings/history", params=params)
history = response.json()

# history["data"] contains list of records:
# [
#   {"timestamp": "...", "tds_ppm": 245.3, "turbidity_ntu": 0.72, "temperature_c": 22.1, ...},
#   ...
# ]
```

---

### E. Sensor Health Status (`GET /api/sensor-health`)
Displays health status of each individual sensor (`ONLINE` / `OFFLINE` / `ERROR`).

```python
response = requests.get(f"{BACKEND_URL}/api/sensor-health")
health = response.json()

# {
#   "sensors": [
#     {
#       "id": 1,
#       "device_id": "esp32-001",
#       "sensor_name": "tds",
#       "status": "ONLINE",
#       "last_seen": "2026-08-29T12:00:00",
#       "last_value": 245.3,
#       "error_count": 0,
#       "updated_at": "2026-08-29T12:00:00"
#     },
#     ...
#   ],
#   "device_online": true
# }
```

---

### F. Alert Management APIs

#### 1. Active Unresolved Alerts:
```python
response = requests.get(f"{BACKEND_URL}/api/alerts/active")
active_alerts = response.json()["data"]
```

#### 2. Filtered Alert History:
```python
params = {"severity": "CRITICAL", "is_resolved": True, "per_page": 50}
response = requests.get(f"{BACKEND_URL}/api/alerts", params=params)
alert_history = response.json()
```

#### 3. Mark Alert Resolved:
```python
alert_id = 5
response = requests.patch(
    f"{BACKEND_URL}/api/alerts/{alert_id}/resolve",
    json={"resolved_by": "operator_admin"}
)
```
