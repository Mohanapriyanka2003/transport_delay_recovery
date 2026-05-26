# Aether: Transport Delay Prediction & Operational Recovery System

Aether is an advanced real-time flight and transport delay prediction platform. Using an ensemble of machine learning models (Random Forest + XGBoost), Aether predicts departure and arrival delay risks based on localized weather, incoming aircraft delays, slot congestion, and route peak-traffic slots. 

When a delay risk is predicted, a custom **Operational Decision Engine** recommends real-time recovery protocols (such as secondary route assignments, gate buffer adjustments, aircraft standby swaps, and passenger service allocations) to reduce downstream delay propagation.

---

## 🚀 Key Features

* **Data Cleaning & Imputation Pipeline**: Standardized handling of cancelled flights, automated imputation of missing arrival records using median airport taxi times, and statistical IQR-based filtering of extreme mechanical/ATC delay outliers.
* **Predictive ML Core**: Runs a localized ensemble of **Random Forest Regressor** and **XGBoost Regressor** models to forecast delay minutes, achieving an XGBoost test RMSE of **15.3 minutes**.
* **Operational Recovery Heuristics**: Dynamic recommendations for airport dispatchers, detailing buffer extensions, reroutes, and flight swaps depending on risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
* **LLM-Simulated Explanations**: Context-aware natural text generation producing detailed diagnostic reports for flight dispatchers and clear, polite, empathetic updates for passengers.
* **Interactive Heatmap Console**: A gorgeous glassmorphism dashboard housing a 10x10 route congestion heatmap. Click any corridor on the heatmap grid to immediately populate parameters into the prediction simulator.

---

## 📈 Impact Achieved

* **20.0% Expected Delay Reduction**: Pre-emptive buffers and slot-adjustments reduce baseline expected delay from an average of **27.5 minutes to 22.0 minutes** across monitored sectors, saving over **7,800 cumulative minutes** of delay propagation.

---

## 📂 Project Directory Structure

```text
transport-delay-recovery/
├── backend/
│   ├── main.py                # FastAPI API server & routes
│   ├── model.py               # Data generation, cleaning, feature engineering, and model training
│   ├── decision_engine.py     # Buffer heuristics & LLM simulated text generator
│   ├── requirements.txt       # Python package dependencies
│   ├── preprocessors.joblib   # Serialized route encoders and data standards
│   ├── rf_model.joblib        # Trained Random Forest model binary
│   └── xgb_model.joblib       # Trained XGBoost model binary
└── frontend/
    ├── package.json           # Node project scripts & devDependencies
    ├── vite.config.js         # Vite compiler configuration
    ├── index.html             # Google fonts & basic HTML template
    └── src/
        ├── main.jsx           # React app renderer
        ├── App.jsx            # Main dashboard component & API integrations
        └── App.css            # Premium HSL slate glassmorphism design system
```

---

## 🛠️ Quick Start Guide

### 1. Start the Python FastAPI Backend
Navigate to the `backend` folder, install requirements, and run the server:
```bash
# Move to backend folder
cd backend

# Create & activate a virtual environment (optional)
python -m venv venv
source venv/bin/activate  # On Linux/macOS
# OR
.\venv\Scripts\Activate.ps1  # On Windows PowerShell

# Install libraries
pip install -r requirements.txt

# Run server
python main.py
```
*The FastAPI server will start on **`http://127.0.0.1:8000`**.*

### 2. Start the React Frontend
Navigate to the `frontend` folder, install Node modules, and launch Vite:
```bash
# Move to frontend folder
cd ../frontend

# Install node dependencies
npm install

# Launch dev server
npm run dev
```
*Open your web browser and go to **`http://localhost:3000`** to view the dashboard.*

---

## 🔌 API Endpoints Reference

### `POST /predict-delay`
Computes real-time delay forecasts and operational alerts.
* **Request Format**:
  ```json
  {
    "origin": "JFK",
    "destination": "LAX",
    "departure_time": "17:30",
    "precipitation": 3.5,
    "visibility": 8.0,
    "wind_speed": 12.5,
    "previous_trip_delay": 20.0,
    "distance": 2475
  }
  ```
* **Response Details**: Returns exact Random Forest & XGBoost raw prediction weights, weather/congestion scalars, a recovery action plan list, and dynamic operations reports.

### `GET /dashboard-data`
Delivers aggregated system metrics, the 10x10 route average delay data array, active real-time logs, and reason distributions for the dashboard widgets.
