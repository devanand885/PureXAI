# PureXAI

**PUREXAI — An Explainable AI Framework for Intelligent Public Drinking Water Quality Monitoring and Predictive Maintenance**

---

## 👥 Team & Responsibilities

| Team Member | Module | Key Responsibilities |
| :--- | :--- | :--- |
| **Barath** | **Hardware & ESP32** | TDS, Turbidity, DS18B20 Sensors, OLED Display, Buzzer & LEDs, Wi-Fi HTTP Transmission |
| **Devanand** | **Backend & Database & Alerts** | FastAPI Backend, SQLite Database, Threshold Engine, Sensor Health & Disconnection Monitoring, REST APIs |
| **Jai Surya** | **Dashboard & AI Analysis** | Streamlit UI, Live & Historical Visualizations, Anomaly Detection, Filter-Health Degradation, Maintenance Reports |

---

## 🏛️ System Architecture

```
       [ ESP32 Microcontroller ]
     (TDS + Turbidity + DS18B20)
                  │
                  ▼ HTTP / Wi-Fi  (POST /api/sensor-data)
       ┌───────────────────────────────┐
       │   FastAPI Backend Gateway     │
       │  (Validation & Error Handling)│
       └──────────────┬────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
 ┌───────────────┐          ┌──────────────────────┐
 │ Threshold     │          │ Sensor Health &      │
 │ Engine        │          │ Disconnection Monitor│
 └──────┬────────┘          └──────────┬───────────┘
        │                              │
        ▼                              ▼
 ┌─────────────────────────────────────────────────┐
 │               SQLite Database                   │
 │ (sensor_readings, sensor_health, alerts tables) │
 └──────────────────────┬──────────────────────────┘
                        │
                        ▼ REST APIs (GET /api/...)
 ┌─────────────────────────────────────────────────┐
 │          Streamlit Dashboard + AI Engine        │
 │ (Live Monitor, Risk Analysis, Maintenance Recs) │
 └─────────────────────────────────────────────────┘
```

> **IMPORTANT ARCHITECTURAL ISOLATION**:
> - ESP32 **never** connects directly to the database.
> - Streamlit dashboard **never** connects directly to the database.
> - The **FastAPI Backend** acts as the single source of truth and communication gateway.

---

## 📁 Repository Structure

```
PureXAI/
├── backend/                  # FastAPI Backend (Devanand)
│   ├── main.py               # Application entry point + APScheduler
│   ├── database.py           # SQLAlchemy SQLite engine (WAL mode)
│   ├── models.py             # ORM models (SensorReading, SensorHealth, Alert)
│   ├── schemas.py            # Pydantic schemas (inbound/outbound)
│   ├── config.py             # Central thresholds, timeouts, and constants
│   ├── requirements.txt      # Python dependencies
│   ├── test_simulation.py    # Complete automated simulated test suite
│   ├── routers/
│   │   ├── esp32.py          # Ingestion (POST /api/sensor-data, GET /api/ping)
│   │   ├── dashboard.py      # Analytics (live, history, status, health, stats)
│   │   └── alerts.py         # Alert management (list, active, resolve)
│   └── services/
│       ├── threshold.py      # Safe/Warning/Unsafe evaluation logic
│       ├── sensor_health.py  # 30s timeout & auto-recovery monitoring
│       ├── alert_service.py  # Alert creation, deduplication & resolution
│       └── disconnection.py  # ESP32 Wi-Fi drop detector
├── esp32/
│   └── README.md             # ESP32 integration guide (Barath)
├── dashboard/
│   └── README.md             # Streamlit dashboard guide (Jai Surya)
├── ai/
│   └── README.md             # AI / ML analysis guide (Jai Surya)
├── data/
│   └── purexai.db            # Local SQLite database (auto-generated)
├── .env.example              # Environment variables template
├── .gitignore
└── README.md                 # Project root documentation
```

---

## ⚙️ Water Quality Thresholds

All thresholds are centralized in `backend/config.py`:

| Parameter | Unit | Safe Range | Warning Range | Unsafe Range |
| :--- | :--- | :--- | :--- | :--- |
| **TDS (Total Dissolved Solids)** | ppm | `< 300.0` | `300.0 – 600.0` | `> 600.0` |
| **Turbidity** | NTU | `< 1.0` | `1.0 – 4.0` | `> 4.0` |
| **Temperature** | °C | `10.0 – 25.0` | `5.0 – 10.0` or `25.0 – 35.0` | `< 5.0` or `> 35.0` |

*Overall water-quality status is determined by the most severe individual parameter status.*

---

## 🚀 Quick Start — Running the Backend

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Start FastAPI Server
```bash
python main.py
```
- **API Base URL**: `http://localhost:8000`
- **Interactive Swagger Documentation**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`

---

## 🧪 Automated Testing with Simulated Data

Before connecting physical hardware, run the comprehensive simulation test suite:
```bash
cd backend
python test_simulation.py
```
This tests:
1. Server liveness (`GET /api/ping`)
2. Payload validation (rejection of negative numbers, NaNs, malformed bodies)
3. Safe water-quality ingestion
4. Threshold violations (TDS, Turbidity, Temperature) and alert generation
5. Alert deduplication (cooldown suppression)
6. Sensor health tracking and 30-second offline timeout
7. ESP32 disconnection detection (`DEVICE_OFFLINE`)
8. Auto-recovery and alert auto-resolution
9. Live readings, historical queries, status, sensor health, and 24h statistics
10. Manual alert resolution (`PATCH /api/alerts/{id}/resolve`)
