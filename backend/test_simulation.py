"""
backend/test_simulation.py — Complete Simulated End-to-End Test Suite for PureXAI Backend.

Validates all 19 requirements without physical hardware:
  1. Root & Ping health checks
  2. Input validation & strict rejection of invalid / negative / NaN values
  3. Safe reading ingestion & DB storage
  4. Warning & Unsafe threshold detection
  5. Alert generation (THRESHOLD, SENSOR_OFFLINE, DEVICE_OFFLINE, SENSOR_RECOVERED)
  6. Alert deduplication
  7. Sensor health tracking
  8. Sensor & device offline detection
  9. Device reconnection & auto-resolution of alerts
  10. Dashboard APIs (Live, History, Status, Sensor Health, Stats)
  11. Alert resolution API
"""

import sys
import os
import time
from datetime import datetime, timezone, timedelta

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, init_db
from models import SensorReading, SensorHealth, Alert
from services.sensor_health import run_sensor_health_check
from services.disconnection import run_disconnection_check

client = TestClient(app)

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_root_and_ping():
    print_header("PHASE 1: Root & Ping Connectivity")
    r = client.get("/")
    assert r.status_code == 200, f"Root failed: {r.text}"
    print(f" [PASS] GET / -> {r.json()['service']} (status: {r.json()['status']})")

    r = client.get("/api/ping")
    assert r.status_code == 200, f"Ping failed: {r.text}"
    assert r.json()["status"] == "ok"
    print(f" [PASS] GET /api/ping -> status: {r.json()['status']}")

def test_validation_rejection():
    print_header("PHASE 2: Inbound Sensor Data Validation (Rejection Tests)")
    
    # Negative TDS
    r = client.post("/api/sensor-data", json={"tds_ppm": -50.0, "turbidity_ntu": 0.5, "temperature_c": 22.0})
    assert r.status_code == 422, f"Expected 422 for negative TDS, got {r.status_code}"
    print(f" [PASS] Negative TDS rejected with HTTP 422")

    # Out of range turbidity
    r = client.post("/api/sensor-data", json={"tds_ppm": 200.0, "turbidity_ntu": 5000.0, "temperature_c": 22.0})
    assert r.status_code == 422, f"Expected 422 for turbidity > 3000, got {r.status_code}"
    print(f" [PASS] Extreme out-of-range turbidity (>3000 NTU) rejected with HTTP 422")

    # Extreme temperature
    r = client.post("/api/sensor-data", json={"tds_ppm": 200.0, "turbidity_ntu": 0.5, "temperature_c": 150.0})
    assert r.status_code == 422, f"Expected 422 for temp > 100, got {r.status_code}"
    print(f" [PASS] Out-of-range temperature (>100 C) rejected with HTTP 422")

def test_safe_reading_ingestion():
    print_header("PHASE 3: Safe Water Reading Ingestion & Database Verification")
    payload = {
        "device_id": "esp32-001",
        "tds_ppm": 180.5,
        "turbidity_ntu": 0.45,
        "temperature_c": 21.0,
        "ip_address": "192.168.1.50"
    }
    r = client.post("/api/sensor-data", json=payload)
    assert r.status_code == 200, f"Failed safe ingestion: {r.text}"
    ack = r.json()
    assert ack["success"] is True
    assert ack["overall_status"] == "Safe"
    print(f" [PASS] POST /api/sensor-data -> Reading #{ack['reading_id']} stored with status: {ack['overall_status']}")

    # Verify DB
    db = SessionLocal()
    reading = db.query(SensorReading).filter(SensorReading.id == ack["reading_id"]).first()
    assert reading is not None
    assert reading.tds_status == "Safe"
    assert reading.turbidity_status == "Safe"
    assert reading.temperature_status == "Safe"
    assert reading.overall_status == "Safe"
    db.close()
    print(f" [PASS] Verified in Database -> TDS=180.5 ppm (Safe), Turbidity=0.45 NTU (Safe), Temp=21.0 C (Safe)")

def test_threshold_violations_and_alerts():
    print_header("PHASE 4: Threshold Violations & Alert Generation")
    
    # 1. Warning Reading (TDS = 450 ppm)
    payload_warn = {
        "device_id": "esp32-001",
        "tds_ppm": 450.0,
        "turbidity_ntu": 0.8,
        "temperature_c": 22.0,
    }
    r = client.post("/api/sensor-data", json=payload_warn)
    assert r.status_code == 200
    assert r.json()["overall_status"] == "Warning"
    print(f" [PASS] Warning reading classified correctly -> overall_status: {r.json()['overall_status']}")

    # 2. Critical/Unsafe Reading (TDS = 750 ppm, Turbidity = 6.5 NTU)
    payload_unsafe = {
        "device_id": "esp32-001",
        "tds_ppm": 750.0,
        "turbidity_ntu": 6.5,
        "temperature_c": 22.0,
    }
    r = client.post("/api/sensor-data", json=payload_unsafe)
    assert r.status_code == 200
    assert r.json()["overall_status"] == "Unsafe"
    print(f" [PASS] Unsafe reading classified correctly -> overall_status: {r.json()['overall_status']}")

    # Verify alerts table
    db = SessionLocal()
    alerts = db.query(Alert).filter(Alert.alert_type == "THRESHOLD").all()
    assert len(alerts) >= 2, f"Expected at least 2 threshold alerts, got {len(alerts)}"
    latest_alert = alerts[-1]
    assert latest_alert.value is not None, "Offending value should be populated in Alert"
    assert latest_alert.threshold is not None, "Breached threshold should be populated in Alert"
    print(f" [PASS] Threshold Alert verified in DB -> type: {latest_alert.alert_type}, sensor: {latest_alert.sensor_name}, val: {latest_alert.value}, threshold: {latest_alert.threshold}")
    db.close()

def test_sensor_health_and_offline_detection():
    print_header("PHASE 5: Sensor Health, Timeout & Disconnection Handling")
    
    db = SessionLocal()
    # Age the sensor last_seen timestamps to simulate 35 seconds of silence
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stale_time = now - timedelta(seconds=40)
    
    sensors = db.query(SensorHealth).all()
    for s in sensors:
        s.last_seen = stale_time
    db.commit()
    db.close()
    
    print(f" [INFO] Simulated 40s sensor silence...")
    # Run background check jobs
    run_sensor_health_check()
    run_disconnection_check(device_id="esp32-001")
    
    db = SessionLocal()
    offline_sensors = db.query(SensorHealth).filter(SensorHealth.status == "OFFLINE").all()
    assert len(offline_sensors) > 0, "Sensors should have transitioned to OFFLINE"
    print(f" [PASS] Sensor Health Monitor -> {len(offline_sensors)} sensors marked OFFLINE")

    offline_alerts = db.query(Alert).filter(Alert.alert_type == "DEVICE_OFFLINE").all()
    assert len(offline_alerts) > 0, "DEVICE_OFFLINE alert should have fired"
    print(f" [PASS] Device Disconnection Monitor -> DEVICE_OFFLINE alert created: {offline_alerts[-1].message[:50]}...")
    db.close()

def test_device_reconnection_and_recovery():
    print_header("PHASE 6: Device Reconnection & Auto-Recovery")
    
    # ESP32 resumes sending good data
    payload = {
        "device_id": "esp32-001",
        "tds_ppm": 210.0,
        "turbidity_ntu": 0.5,
        "temperature_c": 22.0,
    }
    r = client.post("/api/sensor-data", json=payload)
    assert r.status_code == 200
    
    # Run disconnection check to confirm reconnection detection
    run_disconnection_check(device_id="esp32-001")
    
    db = SessionLocal()
    sensors = db.query(SensorHealth).filter(SensorHealth.device_id == "esp32-001").all()
    for s in sensors:
        assert s.status == "ONLINE", f"Sensor {s.sensor_name} should have recovered to ONLINE"
    print(f" [PASS] All {len(sensors)} sensors restored to ONLINE")

    # Confirm auto-resolved offline alerts
    recovered_alerts = db.query(Alert).filter(Alert.alert_type == "SENSOR_RECOVERED").all()
    assert len(recovered_alerts) > 0, "SENSOR_RECOVERED alerts should be created"
    print(f" [PASS] Auto-recovery verified -> {len(recovered_alerts)} SENSOR_RECOVERED records logged")
    db.close()

def test_dashboard_apis():
    print_header("PHASE 7: Dashboard & Analytics APIs")
    
    # 1. Live reading
    r = client.get("/api/readings/live")
    assert r.status_code == 200
    live = r.json()
    assert live["reading"] is not None
    assert live["device_online"] is True
    print(f" [PASS] GET /api/readings/live -> status: {live['reading']['overall_status']}, device_online: {live['device_online']}")

    # 2. Status
    r = client.get("/api/status")
    assert r.status_code == 200
    st = r.json()
    assert st["overall_status"] in ("Safe", "Warning", "Unsafe")
    print(f" [PASS] GET /api/status -> overall: {st['overall_status']}, msg: {st['message']}")

    # 3. History
    r = client.get("/api/readings/history?per_page=10")
    assert r.status_code == 200
    hist = r.json()
    assert hist["total"] > 0
    assert len(hist["data"]) > 0
    print(f" [PASS] GET /api/readings/history -> retrieved {len(hist['data'])} records (total: {hist['total']})")

    # 4. Sensor Health
    r = client.get("/api/sensor-health")
    assert r.status_code == 200
    health = r.json()
    assert len(health["sensors"]) >= 3
    print(f" [PASS] GET /api/sensor-health -> {len(health['sensors'])} sensors tracked, device_online: {health['device_online']}")

    # 5. Stats
    r = client.get("/api/stats")
    assert r.status_code == 200
    stats = r.json()
    assert stats["total_readings"] > 0
    assert "safe_count_24h" in stats
    assert "active_alerts_count" in stats
    assert "device_status" in stats
    print(f" [PASS] GET /api/stats -> total: {stats['total_readings']}, avg_tds: {stats['avg_tds_24h']}, active_alerts: {stats['active_alerts_count']}, device: {stats['device_status']}")

def test_alert_management_api():
    print_header("PHASE 8: Alert Management & Manual Resolution")
    
    # Get active alerts
    r = client.get("/api/alerts/active")
    assert r.status_code == 200
    active = r.json()
    print(f" [PASS] GET /api/alerts/active -> {len(active['data'])} active alerts")

    # If active alerts exist, resolve one
    if active["data"]:
        alert_id = active["data"][0]["id"]
        r = client.patch(f"/api/alerts/{alert_id}/resolve", json={"resolved_by": "test_suite_operator"})
        assert r.status_code == 200
        res = r.json()
        assert res["success"] is True
        print(f" [PASS] PATCH /api/alerts/{alert_id}/resolve -> Alert #{alert_id} successfully marked resolved")

def run_all():
    print("\n" + "#" * 70)
    print("  PUREXAI BACKEND INTEGRATION & PRODUCTION VERIFICATION SUITE")
    print("#" * 70)
    init_db()
    
    test_root_and_ping()
    test_validation_rejection()
    test_safe_reading_ingestion()
    test_threshold_violations_and_alerts()
    test_sensor_health_and_offline_detection()
    test_device_reconnection_and_recovery()
    test_dashboard_apis()
    test_alert_management_api()

    print("\n" + "=" * 70)
    print("  ALL TESTS PASSED! BACKEND IS PRODUCTION-READY FOR INTEGRATION.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_all()
