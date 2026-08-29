# PureXAI — AI & Predictive Analytics Integration Guide (Jai Surya)

This guide documents the API contracts and data pipelines available for the **Explainable AI (XAI) and Predictive Maintenance** modules.

> **ARCHITECTURE NOTE**:
> The AI module runs decoupled from the FastAPI request/response loop.
> It fetches historical and live data from the FastAPI REST endpoints, executes model inference (anomaly detection, filter health degradation, water quality risk analysis), and feeds insights into the Streamlit dashboard.

---

## 1. Available Data Pipelines

### A. Training & Batch Processing Dataset Ingestion
To fetch structured datasets for training ML models or running batch anomaly detection:

```python
import pandas as pd
import requests

BACKEND_URL = "http://localhost:8000"

def fetch_sensor_dataframe(limit: int = 500, start_iso: str = None, end_iso: str = None) -> pd.DataFrame:
    """
    Fetches historical readings from the FastAPI backend and returns a clean Pandas DataFrame.
    """
    params = {"per_page": min(limit, 500)}
    if start_iso:
        params["start_time"] = start_iso
    if end_iso:
        params["end_time"] = end_iso

    response = requests.get(f"{BACKEND_URL}/api/readings/history", params=params)
    response.raise_for_status()
    
    records = response.json().get("data", [])
    if not records:
        return pd.DataFrame()
        
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

# Example Usage:
df = fetch_sensor_dataframe(limit=500)
print(df[["timestamp", "tds_ppm", "turbidity_ntu", "temperature_c", "overall_status"]].head())
```

---

## 2. Recommended AI Modules to Build

### 1. Anomaly Detection (Isolation Forest / One-Class SVM / Autoencoders)
- **Input Features**: `[tds_ppm, turbidity_ntu, temperature_c]` + rolling statistics (e.g. 5-point rolling mean and standard deviation).
- **Output**: Anomaly score (0.0 to 1.0) and boolean flag `is_anomaly`.
- **Explainability (XAI)**: SHAP (SHapley Additive exPlanations) or TreeExplainer values indicating which sensor contributed most to the anomaly.

### 2. Filter-Health & Degradation Trend Analysis
- **Concept**: As water filter membranes degrade, TDS and Turbidity baseline values gradually trend upwards over days/weeks.
- **Method**: Linear/Polynomial regression or ARIMA/Prophet forecasting on 24-hour / 7-day rolling averages.
- **Output**: Remaining Useful Life (RUL) estimate and Maintenance Alert Recommendation.

### 3. Water-Quality Risk Analysis
- **Concept**: Multi-parameter risk index aggregating sudden spikes and rate-of-change (derivative $d/dt$) of TDS and Turbidity.
- **Output**: Water Quality Index (WQI) score (0–100) with confidence interval.

---

## 3. Data Contract Summary

| Feature Column | Data Type | Physical Unit | Expected Normal Range | Anomaly / Spike Threshold |
| :--- | :--- | :--- | :--- | :--- |
| `tds_ppm` | Float | ppm (mg/L) | `50.0 – 299.9` | `> 600.0` or $\Delta > 150$/hr |
| `turbidity_ntu` | Float | NTU | `0.0 – 0.99` | `> 4.0` or $\Delta > 2.0$/hr |
| `temperature_c` | Float | °C | `10.0 – 25.0` | `< 5.0` or `> 35.0` |
| `overall_status` | String | Categorical | `Safe` | `Warning`, `Unsafe` |
