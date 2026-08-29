# PureXAI — ESP32 Hardware Integration Guide (Barath)

This document provides complete instructions for connecting the **ESP32 microcontroller** to the **PureXAI FastAPI Backend**.

---

## 1. Network & Connection Requirements

> **CRITICAL**: The ESP32 and the computer running the FastAPI backend must be connected to the **same Local Area Network (Wi-Fi router or hotspot)**.
> **DO NOT** use `localhost` or `127.0.0.1` inside the ESP32 firmware code. The ESP32 must use your computer's **Local IPv4 address** (e.g. `192.168.1.15`).

### Finding your Backend Computer's LAN IP
- **Windows**: Open Command Prompt / PowerShell and run:
  ```cmd
  ipconfig
  ```
  Look for `IPv4 Address` under your active Wi-Fi or Ethernet adapter (e.g. `192.168.1.42`).

---

## 2. API Endpoints for ESP32

| Purpose | Method | URL Path | Content-Type | Expected Response |
| :--- | :--- | :--- | :--- | :--- |
| **Wi-Fi Connectivity Test** | `GET` | `http://<SERVER_IP>:8000/api/ping` | — | `{"status":"ok", ...}` |
| **Sensor Data Ingestion** | `POST` | `http://<SERVER_IP>:8000/api/sensor-data` | `application/json` | `{"success":true, "overall_status":"Safe", ...}` |

---

## 3. Data Transmission Workflow

1. **Step 1 — Connect to Wi-Fi**: ESP32 boots and connects to SSID/Password.
2. **Step 2 — Ping Backend**: Call `GET http://<SERVER_IP>:8000/api/ping` once to confirm server reachability.
3. **Step 3 — Read Sensors**: Sample TDS, Turbidity, and DS18B20 temperature.
4. **Step 4 — Display Locally**: Update the OLED display with readings & Safe/Warning/Unsafe status.
5. **Step 5 — Transmit Data**: Send HTTP `POST /api/sensor-data` every **5 to 10 seconds**.

---

## 4. Inbound JSON Payload Specification

```json
{
  "device_id": "esp32-001",
  "tds_ppm": 245.3,
  "turbidity_ntu": 0.72,
  "temperature_c": 22.1,
  "ip_address": "192.168.1.55"
}
```

### Field Descriptions:
- `device_id` *(string, optional, default: `"esp32-001"`)*: Unique device identifier.
- `tds_ppm` *(float, optional)*: Total Dissolved Solids in ppm (Range: `0.0` to `5000.0`).
- `turbidity_ntu` *(float, optional)*: Turbidity in NTU (Range: `0.0` to `3000.0`).
- `temperature_c` *(float, optional)*: Water temperature in °C (Range: `-10.0` to `100.0`).
- `ip_address` *(string, optional)*: ESP32's current assigned IP on the local network.

> **Note**: If an individual sensor fails or is disconnected, send `null` for that specific field (or omit it). The backend will mark that individual sensor as offline while continuing to process the remaining operational sensors.

---

## 5. Backend Response Specification

### Successful Response (`200 OK`)
```json
{
  "success": true,
  "reading_id": 104,
  "overall_status": "Safe",
  "timestamp": "2026-08-29T12:00:00",
  "message": "Reading stored. Status: Safe"
}
```

### Validation Failure (`422 Unprocessable Entity`)
If negative values, NaN, or out-of-range numbers are sent:
```json
{
  "detail": [
    {
      "loc": ["body", "tds_ppm"],
      "msg": "Input should be greater than or equal to 0",
      "type": "greater_than_equal"
    }
  ]
}
```

---

## 6. Sensor Health & Disconnection Rules

- **Sending Interval**: Send data every **5–10 seconds**.
- **Sensor Offline Timeout**: If any individual sensor fails to send data for **> 30 seconds**, the backend marks that sensor `OFFLINE` and generates a `SENSOR_OFFLINE` alert.
- **ESP32 Disconnection Timeout**: If no data is received from the entire device for **> 30 seconds**, the backend marks the device `OFFLINE` and triggers a `DEVICE_OFFLINE` critical alert.
- **Auto-Recovery**: When readings resume, the backend automatically sets the status back to `ONLINE`, auto-resolves outstanding offline alerts, and creates a `SENSOR_RECOVERED` info log.

---

## 7. Arduino / C++ Code Snippet Example

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Make backend host and port easily configurable
const char* serverHost = "192.168.1.42"; 
const int serverPort = 8000;

void sendSensorData(float tds, float turbidity, float temperature) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = "http://" + String(serverHost) + ":" + String(serverPort) + "/api/sensor-data";
    
    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;
    doc["device_id"] = "esp32-001";
    doc["tds_ppm"] = tds;
    doc["turbidity_ntu"] = turbidity;
    doc["temperature_c"] = temperature;
    doc["ip_address"] = WiFi.localIP().toString();

    String requestBody;
    serializeJson(doc, requestBody);

    int httpResponseCode = http.POST(requestBody);
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("Server Response: " + response);
    } else {
      Serial.printf("HTTP POST failed, error: %s\n", http.errorToString(httpResponseCode).c_str());
    }
    http.end();
  }
}
```
