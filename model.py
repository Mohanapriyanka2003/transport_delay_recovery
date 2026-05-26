import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error, r2_score
import xgboost as xgb

# Set random seed for reproducibility
np.random.seed(42)

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
RF_MODEL_PATH = os.path.join(MODEL_DIR, "rf_model.joblib")
XGB_MODEL_PATH = os.path.join(MODEL_DIR, "xgb_model.joblib")
PREPROCESSORS_PATH = os.path.join(MODEL_DIR, "preprocessors.joblib")

# Predefined metadata for routes
AIRPORTS = ["JFK", "LAX", "ORD", "DFW", "ATL", "SFO", "MIA", "SEA", "DEN", "BOS"]

def generate_simulated_data(num_samples=10000):
    """
    Generates a realistic flight delay dataset with weather, cancellations,
    and missing values to simulate real-world data cleaning scenarios.
    """
    print(f"Generating {num_samples} simulated flight operations records...")
    
    # Base fields
    origins = np.random.choice(AIRPORTS, size=num_samples)
    destinations = []
    for orig in origins:
        dest_choices = [a for a in AIRPORTS if a != orig]
        destinations.append(np.random.choice(dest_choices))
    destinations = np.array(destinations)
    
    # Distance based on airports (simple proxy mapping)
    # Just a deterministic distance matrix or random with some structure
    distance = np.random.randint(200, 2600, size=num_samples)
    
    # Date & time fields (past 30 days)
    timestamps = pd.date_range(start="2026-04-26", end="2026-05-26", periods=num_samples)
    
    # Weather parameters
    precipitation = np.random.exponential(scale=2.0, size=num_samples) # mm
    visibility = np.clip(np.random.normal(loc=9.0, scale=3.0, size=num_samples), 0, 10) # miles
    wind_speed = np.random.weibull(a=2.0, size=num_samples) * 15 # mph
    
    # Operational fields
    taxi_out = np.random.gamma(shape=3.0, scale=5.0, size=num_samples) + 5 # 5 to 60 mins
    taxi_in = np.random.gamma(shape=2.0, scale=4.0, size=num_samples) + 3 # 3 to 40 mins
    
    # Previous trip delay (delay propagation)
    previous_trip_delay = np.random.exponential(scale=15.0, size=num_samples)
    # Zero out previous delay for 60% of flights (first flight of day, etc.)
    previous_trip_delay[np.random.rand(num_samples) > 0.4] = 0.0
    
    # Cancellations (approx 3% of flights)
    cancellation_prob = 0.02 + 0.1 * (precipitation > 8.0) + 0.1 * (visibility < 1.5) + 0.08 * (wind_speed > 35)
    cancelled = np.random.rand(num_samples) < cancellation_prob
    
    # Departure Delay (strongly influenced by previous delay, peak hours, and weather)
    peak_hour_flag = ((timestamps.hour >= 7) & (timestamps.hour <= 10)) | ((timestamps.hour >= 16) & (timestamps.hour <= 19))
    weather_impact = (precipitation * 5.0) + ((10 - visibility) * 4.0) + (wind_speed * 0.8)
    
    # Route base delays (congested routes like JFK-LAX or ORD-LGA)
    route_factors = []
    for o, d in zip(origins, destinations):
        if (o == "JFK" and d == "LAX") or (o == "ORD" and d == "LGA") or (o == "ATL" and d == "ORD"):
            route_factors.append(np.random.normal(loc=25.0, scale=10.0))
        else:
            route_factors.append(np.random.normal(loc=5.0, scale=5.0))
    route_factors = np.array(route_factors)
    
    dep_delay_base = (
        0.5 * previous_trip_delay + 
        weather_impact + 
        (peak_hour_flag * 12.0) + 
        route_factors + 
        np.random.normal(loc=2.0, scale=8.0, size=num_samples)
    )
    # Clamp dep_delay to positive if flight runs, otherwise set to NaN if cancelled
    dep_delay = np.clip(dep_delay_base, -10, 500)
    dep_delay[cancelled] = np.nan
    
    # Arrival Delay (strongly correlated with dep delay and taxi times)
    arr_delay = dep_delay + taxi_out + taxi_in - 25.0 + np.random.normal(loc=0, scale=5.0, size=num_samples)
    arr_delay[cancelled] = np.nan
    
    # Create outliers (extreme delays due to air traffic control or mechanical issues)
    outlier_idx = np.random.choice(num_samples, size=int(num_samples * 0.015), replace=False)
    for idx in outlier_idx:
        if not cancelled[idx]:
            dep_delay[idx] = np.random.randint(240, 720) # 4 to 12 hours delay
            arr_delay[idx] = dep_delay[idx] + np.random.randint(10, 45)
            
    # Inject missing actual arrival times for non-cancelled flights (say 1% system noise)
    missing_arr_idx = np.random.choice(num_samples, size=int(num_samples * 0.01), replace=False)
    for idx in missing_arr_idx:
        if not cancelled[idx]:
            arr_delay[idx] = np.nan

    # Build DataFrame
    df = pd.DataFrame({
        "timestamp": timestamps,
        "origin": origins,
        "destination": destinations,
        "distance": distance,
        "precipitation": precipitation,
        "visibility": visibility,
        "wind_speed": wind_speed,
        "taxi_out": taxi_out,
        "taxi_in": taxi_in,
        "previous_trip_delay": previous_trip_delay,
        "cancelled": cancelled.astype(int),
        "departure_delay": dep_delay,
        "arrival_delay": arr_delay
    })
    
    return df

def clean_data(df):
    """
    Cleans the raw simulated transport dataset by:
    1. Handling cancelled trips (removing them from numerical delay training).
    2. Imputing or handling missing actual arrival times.
    3. Filtering out extreme delay outliers (z-score/IQR) and logging the impact.
    """
    print("\n--- Data Cleaning Pipeline ---")
    initial_shape = df.shape[0]
    
    # 1. Filter out cancelled trips
    cancelled_count = df[df["cancelled"] == 1].shape[0]
    df_cleaned = df[df["cancelled"] == 0].copy()
    print(f"Removed {cancelled_count} cancelled flights from delay training dataset.")
    
    # 2. Handle missing actual arrival times
    # Non-cancelled flights with missing arrival delays are dropped or imputed.
    # Since arrival_delay is our target, dropping is safest, but we can also impute via departure_delay if dep_delay exists.
    missing_arr_before = df_cleaned["arrival_delay"].isna().sum()
    
    # Drop rows where BOTH departure and arrival are missing
    df_cleaned = df_cleaned.dropna(subset=["departure_delay"])
    
    # Impute missing arrival delays using departure delay + median taxi times
    median_taxi_out = df_cleaned["taxi_out"].median()
    median_taxi_in = df_cleaned["taxi_in"].median()
    
    missing_arr_mask = df_cleaned["arrival_delay"].isna()
    df_cleaned.loc[missing_arr_mask, "arrival_delay"] = (
        df_cleaned.loc[missing_arr_mask, "departure_delay"] + 
        median_taxi_out + median_taxi_in - 25.0
    )
    
    print(f"Imputed {missing_arr_before} missing arrival delays using departure delays and median taxi times.")
    
    # 3. Filter extreme delay outliers
    # We will define outliers as arrival delays above Q3 + 3 * IQR (extremely conservative)
    # Or delay greater than 360 minutes (6 hours)
    q1 = df_cleaned["arrival_delay"].quantile(0.25)
    q3 = df_cleaned["arrival_delay"].quantile(0.75)
    iqr = q3 - q1
    upper_bound = q3 + 3.0 * iqr
    
    outliers = df_cleaned[df_cleaned["arrival_delay"] > upper_bound]
    outliers_count = outliers.shape[0]
    
    # Clip extreme delays to the upper bound rather than dropping, or drop them to clean training
    # Let's drop them to let the model learn normal/moderate delay behavior accurately,
    # and document that mechanical breakdowns (>6 hrs) are handled separately.
    df_cleaned = df_cleaned[df_cleaned["arrival_delay"] <= upper_bound].copy()
    print(f"Detected and removed {outliers_count} extreme delay outliers (Arrival Delay > {upper_bound:.1f} mins).")
    
    final_shape = df_cleaned.shape[0]
    print(f"Data cleaning completed. Rows retained: {final_shape}/{initial_shape} ({final_shape/initial_shape*100:.1f}%)")
    
    return df_cleaned

def engineer_features(df, fit_preprocessors=False, preprocessors=None):
    """
    Performs feature engineering on the cleaned dataset:
    1. Route congestion score: delay rates per route.
    2. Weather severity score: composite index of wind, rain, and visibility.
    3. Peak-hour flag: binary indicator for rush hours.
    4. Previous-trip delay: propagating delay.
    """
    df = df.copy()
    
    # 1. Peak-hour flag
    # Peak hours: 7 AM - 10 AM, 4 PM - 7 PM (16:00-19:00)
    hour = pd.to_datetime(df["timestamp"]).dt.hour
    df["peak_hour"] = (((hour >= 7) & (hour <= 10)) | ((hour >= 16) & (hour <= 19))).astype(int)
    
    # 2. Weather severity score (0 to 10 scale)
    # Higher precipitation, higher wind, lower visibility -> higher severity
    norm_precip = df["precipitation"] / 10.0 # scale by 10mm
    norm_wind = df["wind_speed"] / 40.0 # scale by 40mph
    norm_vis = (10.0 - df["visibility"]) / 10.0 # invert and scale vis (10 is perfect visibility)
    
    df["weather_severity"] = np.clip((norm_precip * 3.5 + norm_wind * 3.0 + norm_vis * 3.5), 0, 10)
    
    # 3. Route Congestion Score
    # We calculate the average historical delay for each (origin, destination) route
    df["route"] = df["origin"] + "-" + df["destination"]
    
    if fit_preprocessors:
        # Save historical congestion mapping
        route_congestion = df.groupby("route")["arrival_delay"].mean().to_dict()
        # Default overall mean for unseen routes
        overall_mean = df["arrival_delay"].mean()
        route_congestion["DEFAULT"] = overall_mean
        
        # Label Encoder for routes
        le_route = LabelEncoder()
        df["route_encoded"] = le_route.fit_transform(df["route"])
        
        preprocessors = {
            "route_congestion": route_congestion,
            "le_route": le_route,
            "overall_mean": overall_mean
        }
    else:
        if preprocessors is None:
            raise ValueError("Preprocessors must be provided if fit_preprocessors is False")
        
        rc_map = preprocessors["route_congestion"]
        overall_mean = preprocessors["overall_mean"]
        
        df["route_encoded"] = preprocessors["le_route"].transform(df["route"])
        
    df["route_congestion_score"] = df["route"].map(preprocessors["route_congestion"]).fillna(preprocessors["overall_mean"])
    
    return df, preprocessors

def train_and_evaluate():
    """
    Main pipeline to generate data, clean, engineer features, train
    Random Forest and XGBoost, evaluate their performance, and save preprocessors/models.
    """
    # 1. Generate & Clean
    raw_df = generate_simulated_data(12000)
    cleaned_df = clean_data(raw_df)
    
    # 2. Feature Engineering
    engineered_df, preprocessors = engineer_features(cleaned_df, fit_preprocessors=True)
    
    # Prepare features and target
    feature_cols = [
        "distance", "peak_hour", "weather_severity", 
        "previous_trip_delay", "route_congestion_score"
    ]
    X = engineered_df[feature_cols]
    y = engineered_df["arrival_delay"]
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("\n--- Training Machine Learning Models ---")
    
    # 1. Random Forest Regressor
    print("Training Random Forest Regressor...")
    rf_model = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
    rf_model.fit(X_train, y_train)
    
    # 2. XGBoost Regressor
    print("Training XGBoost Regressor...")
    xgb_model = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.08, random_state=42, n_jobs=-1)
    xgb_model.fit(X_train, y_train)
    
    # Evaluate RF
    rf_preds = rf_model.predict(X_test)
    rf_rmse = np.sqrt(mean_squared_error(y_test, rf_preds))
    rf_r2 = r2_score(y_test, rf_preds)
    print(f"Random Forest - Test RMSE: {rf_rmse:.3f} mins, R2 Score: {rf_r2:.3f}")
    
    # Evaluate XGB
    xgb_preds = xgb_model.predict(X_test)
    xgb_rmse = np.sqrt(mean_squared_error(y_test, xgb_preds))
    xgb_r2 = r2_score(y_test, xgb_preds)
    print(f"XGBoost - Test RMSE: {xgb_rmse:.3f} mins, R2 Score: {xgb_r2:.3f}")
    
    # Save models and preprocessors
    print(f"\nSaving preprocessors and models to {MODEL_DIR}...")
    joblib.dump(preprocessors, PREPROCESSORS_PATH)
    joblib.dump(rf_model, RF_MODEL_PATH)
    joblib.dump(xgb_model, XGB_MODEL_PATH)
    print("Training pipeline completed successfully.")
    
    return {
        "rf_rmse": rf_rmse,
        "rf_r2": rf_r2,
        "xgb_rmse": xgb_rmse,
        "xgb_r2": xgb_r2
    }

def predict_single(input_data):
    """
    Perform feature engineering and delay prediction for a single request.
    input_data structure:
    {
        "origin": str,
        "destination": str,
        "departure_time": str (HH:MM),
        "precipitation": float,
        "visibility": float,
        "wind_speed": float,
        "previous_trip_delay": float,
        "distance": float
    }
    """
    # Load assets
    preprocessors = joblib.load(PREPROCESSORS_PATH)
    rf_model = joblib.load(RF_MODEL_PATH)
    xgb_model = joblib.load(XGB_MODEL_PATH)
    
    # Parse peak hour
    try:
        hour = int(input_data["departure_time"].split(":")[0])
    except Exception:
        hour = 12
    peak_hour = 1 if ((hour >= 7 and hour <= 10) or (hour >= 16 and hour <= 19)) else 0
    
    # Weather severity
    precipitation = float(input_data["precipitation"])
    visibility = float(input_data["visibility"])
    wind_speed = float(input_data["wind_speed"])
    
    norm_precip = precipitation / 10.0
    norm_wind = wind_speed / 40.0
    norm_vis = (10.0 - visibility) / 10.0
    weather_severity = np.clip((norm_precip * 3.5 + norm_wind * 3.0 + norm_vis * 3.5), 0, 10)
    
    # Route congestion score
    route = input_data["origin"] + "-" + input_data["destination"]
    rc_map = preprocessors["route_congestion"]
    default_rc = preprocessors["overall_mean"]
    route_congestion_score = rc_map.get(route, rc_map.get(f"{input_data['destination']}-{input_data['origin']}", default_rc))
    
    # Assemble feature vector
    features = pd.DataFrame([{
        "distance": float(input_data["distance"]),
        "peak_hour": peak_hour,
        "weather_severity": weather_severity,
        "previous_trip_delay": float(input_data["previous_trip_delay"]),
        "route_congestion_score": route_congestion_score
    }])
    
    # Predict
    rf_pred = rf_model.predict(features)[0]
    xgb_pred = xgb_model.predict(features)[0]
    
    # Ensemble prediction (average of both)
    predicted_delay = float(np.clip(0.6 * xgb_pred + 0.4 * rf_pred, 0, 480))
    
    return {
        "predicted_delay_minutes": predicted_delay,
        "weather_severity_score": float(weather_severity),
        "route_congestion_score": float(route_congestion_score),
        "peak_hour_flag": peak_hour,
        "rf_prediction": float(np.clip(rf_pred, 0, 480)),
        "xgb_prediction": float(np.clip(xgb_pred, 0, 480))
    }

if __name__ == "__main__":
    train_and_evaluate()
