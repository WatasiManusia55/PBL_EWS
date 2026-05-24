import time
import os
import joblib
import pandas as pd
from collections import deque

# ==================================================
# CONFIG
# ==================================================

MODEL_PATH = "flood_early_warning_rf_model.pkl"
LOG_PATH = "flood_log.csv"

CSV_SENSOR_PATH = "/home/pi/Downloads/PBL_EWS_NEW/PBL_EWS/sensor_data.csv"

SENSOR_INTERVAL_SECONDS = 30

MIN_HISTORY_FOR_PREDICTION = 60
MAX_HISTORY = 720

SENSOR_HEIGHT_M = 2.0

# ==================================================
# LOAD MODEL
# ==================================================

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(MODEL_PATH)

model_data = joblib.load(MODEL_PATH)

rf = model_data["rf"]
features = model_data["features"]
threshold = model_data["threshold"]

print("===================================")
print("Flood Early Warning System Started")
print("Threshold:", threshold)
print("===================================")

# ==================================================
# BUFFER
# ==================================================

history = deque(maxlen=MAX_HISTORY)
last_timestamp = None
file_pointer = 0

# ==================================================
# STATUS
# ==================================================

def get_siaga_status(pred_alert, water_level_m):
    if pred_alert == 0:
        return "AMAN"
    elif water_level_m <= 1.0:
        return "SIAGA 1"
    elif water_level_m <= 1.3:
        return "SIAGA 2"
    else:
        return "SIAGA 3"

# ==================================================
# READ SENSOR (STREAM STYLE FIXED)
# ==================================================

def read_sensor():
    global file_pointer

    df = pd.read_csv(CSV_SENSOR_PATH)

    if df.empty:
        return None

    # kalau belum ada data baru
    if file_pointer >= len(df):
        return None

    row = df.iloc[file_pointer]
    file_pointer += 1

    return {
        "timestamp": pd.to_datetime(row["waktu"]),
        "suhu": float(row["suhu"]),
        "kelembapan": float(row["kelembapan"]),
        "tekanan": float(row["tekanan"]),
        "jarak_air": float(row["jarak_air"]),
        "rain_rate": float(row["rain_rate"])
    }

# ==================================================
# CONVERT
# ==================================================

def convert_sensor_data(raw):

    distance_m = raw["jarak_air"] / 1000.0
    water_level = SENSOR_HEIGHT_M - distance_m

    if water_level < 0:
        water_level = 0.0

    return {
        "timestamp": raw["timestamp"],
        "Temperature_C": raw["suhu"],
        "Humidity_percent": raw["kelembapan"],
        "SeaLevelPressure_hPa": raw["tekanan"],
        "Precipitation_mm": raw["rain_rate"],
        "RiverWaterLevel_m": water_level
    }

# ==================================================
# FEATURES
# ==================================================

def build_features(current):

    history.append(current)

    df = pd.DataFrame(list(history))

    current_water = current["RiverWaterLevel_m"]

    rain_30 = df["Precipitation_mm"].tail(60).sum()
    rain_1h = df["Precipitation_mm"].tail(120).sum()
    rain_3h = df["Precipitation_mm"].tail(360).sum()
    rain_6h = df["Precipitation_mm"].tail(720).sum()

    def delta(p):
        if len(df) >= p:
            return current_water - df["RiverWaterLevel_m"].iloc[-p]
        return 0.0

    X = pd.DataFrame([{
        "Temperature_C": current["Temperature_C"],
        "Humidity_percent": current["Humidity_percent"],
        "Precipitation_mm": current["Precipitation_mm"],
        "SeaLevelPressure_hPa": current["SeaLevelPressure_hPa"],
        "RiverWaterLevel_m": current_water,

        "Rain_30min": rain_30,
        "Rain_1h": rain_1h,
        "Rain_3h": rain_3h,
        "Rain_6h": rain_6h,

        "WaterLevel_Change_30min": delta(60),
        "WaterLevel_Change_1h": delta(120),
        "WaterLevel_Change_3h": delta(360)
    }])

    return X

# ==================================================
# PREDICT
# ==================================================

def predict(X):

    X = X[features]

    prob = rf.predict_proba(X)[:, 1][0]

    alert = int(prob >= threshold)

    return prob, alert

# ==================================================
# LOG
# ==================================================

def save_log(t, w, p, a, status):

    file_exists = os.path.exists(LOG_PATH)

    pd.DataFrame([{
        "timestamp": t,
        "water_level": w,
        "prob": p,
        "alert": a,
        "status": status
    }]).to_csv(
        LOG_PATH,
        mode="a",
        header=not file_exists,
        index=False
    )

# ==================================================
# LOOP
# ==================================================

print("System running...")

while True:

    try:

        raw = read_sensor()

        if raw is None:
            print("No new data")
            time.sleep(3)
            continue

        if raw["timestamp"] == last_timestamp:
            time.sleep(2)
            continue

        last_timestamp = raw["timestamp"]

        data = convert_sensor_data(raw)

        X = build_features(data)

        if len(history) < MIN_HISTORY_FOR_PREDICTION:
            print(f"Collecting {len(history)}/{MIN_HISTORY_FOR_PREDICTION}")
            time.sleep(SENSOR_INTERVAL_SECONDS)
            continue

        prob, alert = predict(X)

        status = get_siaga_status(alert, data["RiverWaterLevel_m"])

        print("\n====================")
        print("Time :", data["timestamp"])
        print("Water:", round(data["RiverWaterLevel_m"], 3))
        print("Prob :", round(prob, 4))
        print("Status:", status)
        print("====================")

        save_log(
            data["timestamp"],
            data["RiverWaterLevel_m"],
            prob,
            alert,
            status
        )

        time.sleep(SENSOR_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("Stopped")
        break

    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)