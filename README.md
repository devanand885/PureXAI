# PureXAI

**PureXAI** is an IoT-based Water Quality Monitoring System that uses an ESP32 microcontroller with TDS, turbidity, and temperature sensors to monitor water quality in real time. Data is sent to a Python/FastAPI backend, stored in a database, analyzed for safety thresholds, and displayed on a Streamlit dashboard with AI-powered anomaly detection.

---

## Team

| Member | Role |
|--------|------|
| **Barath** | Sensors + ESP32 + Hardware |
| **Devanand** | Backend + Database + Alerts |
| **Jai Surya** | Dashboard + AI + Analysis |

---

## Project Structure

```
PureXAI/
├── backend/         # Python/FastAPI backend (Devanand)
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── config.py
│   ├── requirements.txt
│   ├── routers/
│   │   ├── esp32.py
│   │   ├── dashboard.py
│   │   └── alerts.py
│   ├── services/
│   │   ├── threshold.py
│   │   ├── sensor_health.py
│   │   ├── alert_service.py
│   │   └── disconnection.py
│   └── README.md
└── README.md
```

---

## Quick Start (Backend)

```bash
cd backend
pip install -r requirements.txt
python main.py
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

---

## Sensors Used

- **TDS Sensor** — Total Dissolved Solids (water purity)
- **Turbidity Sensor** — Water clarity / cloudiness
- **DS18B20** — Water temperature
- **OLED Display** — Local real-time display on ESP32
- **LEDs + Buzzer** — Local Safe/Warning/Unsafe indicators

---

## Water Quality Thresholds

| Parameter | Safe | Warning | Unsafe |
|-----------|------|---------|--------|
| TDS | < 300 ppm | 300–600 ppm | > 600 ppm |
| Turbidity | < 1 NTU | 1–4 NTU | > 4 NTU |
| Temperature | 10–25°C | 5–35°C (edges) | < 5°C or > 35°C |
