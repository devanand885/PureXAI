# PureXAI — Backend API

FastAPI backend for the PureXAI Water Quality Monitoring System.  
Receives sensor data from an ESP32, stores it in SQLite, checks water quality thresholds, monitors sensor health, and exposes REST APIs for the Streamlit dashboard.

---

## Quick Start

### 1. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Run the server
```bash
python main.py
# OR with uvicorn directly:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Open Swagger UI
Navigate to **http://localhost:8000/docs** to explore and test all endpoints interactively.

---

## Project Structure

```
backend/
├── main.py                  # FastAPI app + startup
├── database.py              # SQLAlchemy engine & session
├── models.py                # ORM models (SensorReading, Alert, SensorHealth)
├── schemas.py               # Pydantic request/response schemas
├── config.py                # Thresholds, constants, settings
├── routers/
│   ├── esp32.py             # POST /api/sensor-data  (ESP32 ingestion)
│   ├── dashboard.py         # GET  /api/readings/*   (dashboard read APIs)
│   └── alerts.py            # GET/PATCH /api/alerts  (alert management)
└── services/
    ├── threshold.py         # Water quality threshold evaluation
    ├── sensor_health.py     # Per-sensor health monitoring
    ├── alert_service.py     # Alert creation, dedup, notification
    └── disconnection.py     # ESP32 disconnection detection
```

---

## API Reference

### ESP32 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sensor-data` | Receive sensor data from ESP32 |
| `GET`  | `/api/ping` | Server liveness check for ESP32 |

#### ESP32 POST Payload Example
```json
{
  "tds_ppm": 245.3,
  "turbidity_ntu": 0.72,
  "temperature_c": 22.1,
  "device_id": "esp32-001",
  "ip_address": "192.168.1.42"
}
```

#### ESP32 Response Example
```json
{
  "success": true,
  "reading_id": 42,
  "overall_status": "Safe",
  "timestamp": "2026-08-23T17:00:00Z",
  "message": "Reading stored. Status: Safe"
}
```

---

### Dashboard Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/readings/live` | Latest reading + device online status |
| `GET` | `/api/readings/history` | Paginated historical data with filters |
| `GET` | `/api/status` | Current water quality status |
| `GET` | `/api/sensor-health` | Per-sensor health status |
| `GET` | `/api/stats` | 24-hour aggregate statistics |

#### History Query Parameters
| Param | Type | Description |
|-------|------|-------------|
| `page` | int | Page number (default: 1) |
| `per_page` | int | Records per page (default: 50, max: 500) |
| `start_time` | ISO datetime | Filter by start time |
| `end_time` | ISO datetime | Filter by end time |
| `status` | string | `Safe` / `Warning` / `Unsafe` |
| `device_id` | string | Filter by device |

---

### Alert Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/alerts` | Paginated alert history with filters |
| `GET` | `/api/alerts/active` | All unresolved alerts |
| `PATCH` | `/api/alerts/{id}/resolve` | Resolve an alert manually |

---

## Water Quality Thresholds

| Parameter | Safe | Warning | Unsafe |
|-----------|------|---------|--------|
| TDS | < 300 ppm | 300–600 ppm | > 600 ppm |
| Turbidity | < 1 NTU | 1–4 NTU | > 4 NTU |
| Temperature | 10–25 °C | 5–10°C or 25–35°C | < 5°C or > 35°C |

---

## Sensor Health Monitoring

- Background job runs every **15 seconds**
- If a sensor sends no data for **30 seconds** → marked `OFFLINE`
- `SENSOR_OFFLINE` alert is created (with 60s dedup cooldown)
- When data resumes → sensor marked `ONLINE`, alerts auto-resolved
- If **all sensors** are silent → `DEVICE_OFFLINE` alert (ESP32 disconnected)

---

## Alert Types

| Type | Severity | Trigger |
|------|----------|---------|
| `THRESHOLD` | WARNING / CRITICAL | Parameter exceeds threshold |
| `SENSOR_OFFLINE` | WARNING | Single sensor silent >30s |
| `DEVICE_OFFLINE` | CRITICAL | All sensors silent >30s |
| `SENSOR_RECOVERED` | INFO | Sensor/device back online |

---

## Database

- **Engine**: SQLite (`data/purexai.db`) — auto-created on first run
- **Tables**: `sensor_readings`, `sensor_health`, `alerts`
- **Upgrade path**: Change `DATABASE_URL` in `config.py` to PostgreSQL with no code changes

---

## Environment Variables (`.env`)

```env
DEBUG=True
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite:///./data/purexai.db
```

---

## Integration with Streamlit Dashboard

All dashboard endpoints return JSON. In Streamlit (Jai Surya's work), use:
```python
import requests
BASE_URL = "http://localhost:8000"

# Live reading
live = requests.get(f"{BASE_URL}/api/readings/live").json()

# 24h stats
stats = requests.get(f"{BASE_URL}/api/stats").json()

# Alert history
alerts = requests.get(f"{BASE_URL}/api/alerts", params={"is_resolved": False}).json()
```

---

## Integration with ESP32 (Barath's Work)

Point the ESP32 HTTP POST to:
```
http://<server-ip>:8000/api/sensor-data
```
Content-Type: `application/json`  
Send readings every 5–10 seconds. The server returns a JSON ACK with the status.
