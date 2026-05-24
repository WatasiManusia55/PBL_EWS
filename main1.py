import time
import os
import math
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

# 30 detik interval:
# 30 menit = 60 data
# 1 jam    = 120 data
# 3 jam    = 360 data
# 6 jam    = 720 data
MIN_HISTORY_FOR_PREDICTION = 60
MAX_HISTORY = 720

# jarak_air dari sensor/gateway dalam millimeter
JARAK_AIR_DIVISOR = 1000.0

# ==================================================
# RULE-BASED CONFIG
# Sumber: Data lapangan dari pak RT
# ==================================================

# Luas total wilayah RT dalam Ha
TOTAL_AREA_HA = 6.0

# Jumlah KK total di RT
TOTAL_KK = 35  # estimasi tengah dari 30-40 KK

# Kepadatan KK per Ha (35 KK / 6 Ha)
KK_PER_HA = TOTAL_KK / TOTAL_AREA_HA

# Persentase luas terdampak per siaga
# Sumber: Model dosen + kalibrasi data lapangan (banjir ~2Ha = ~33% dari 6Ha)
SIAGA_3_DAMPAK_PERSEN = 0.20   # 10-30%, tengah = 20%
SIAGA_2_DAMPAK_PERSEN = 0.45   # 31-60%, tengah = 45%
SIAGA_1_DAMPAK_PERSEN = 0.70   # >60%, estimasi 70%

# Bantuan per KK per siaga
# Sumber: Data real pak RT (Rp300rb - Rp1jt tergantung kerusakan)
BANTUAN_PER_KK = {
    "SIAGA 3": 350_000,    # kerusakan ringan
    "SIAGA 2": 650_000,    # kerusakan sedang
    "SIAGA 1": 1_000_000,  # kerusakan berat
}

# ==================================================
# LOAD MODEL
# ==================================================

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model tidak ditemukan: {MODEL_PATH}")

model_data = joblib.load(MODEL_PATH)

rf = model_data["rf"]
features = model_data["features"]
threshold = model_data["threshold"]

print("===================================")
print("Flood Early Warning System Started")
print("Random Forest Model Loaded Successfully")
print("Threshold :", threshold)
print("Features  :", features)
print("===================================")

# ==================================================
# HISTORY BUFFER
# ==================================================

history = deque(maxlen=MAX_HISTORY)
last_timestamp = None
file_pointer = 0

# ==================================================
# STATUS SIAGA FINAL
# ==================================================
# distance_to_water_m = jarak sensor ultrasonic ke permukaan air
# BUKAN tinggi air dari dasar sungai
#
# Semakin kecil jarak:
# -> air semakin dekat sensor
# -> permukaan air naik
# -> risiko banjir meningkat
#
# SIAGA 3 = aman / normal
# SIAGA 2 = air hampir meluap
# SIAGA 1 = banjir / darurat
# ==================================================

def get_siaga_status(pred_alert, distance_to_water_m):
    if pred_alert == 0:
        return "SIAGA 3"

    if distance_to_water_m <= 1.0:
        return "SIAGA 1"

    if distance_to_water_m <= 1.3:
        return "SIAGA 2"

    return "SIAGA 3"


# ==================================================
# ESTIMASI DAMPAK
# Sumber: Model dosen + data lapangan pak RT
#
# Formula:
# Luas terdampak (Ha) = % dampak x luas total (Ha)
# KK terdampak        = luas terdampak (Ha) x KK per Ha
# Total dana          = KK terdampak x bantuan per KK
# ==================================================

def estimate_affected_area_ha(status_siaga):
    """Luas terdampak dalam Ha berdasarkan status siaga."""
    if status_siaga == "SIAGA 1":
        persen = SIAGA_1_DAMPAK_PERSEN
    elif status_siaga == "SIAGA 2":
        persen = SIAGA_2_DAMPAK_PERSEN
    else:
        persen = SIAGA_3_DAMPAK_PERSEN

    return round(persen * TOTAL_AREA_HA, 2)


def ha_to_m2(ha):
    return int(ha * 10_000)


def estimate_affected_kk(area_ha):
    """Estimasi KK terdampak dari luas area."""
    kk = area_ha * KK_PER_HA
    return min(int(round(kk)), TOTAL_KK)  # tidak melebihi total KK di RT


def estimate_budget(affected_kk, status_siaga):
    """Total dana bantuan = KK terdampak x bantuan per KK sesuai siaga."""
    bantuan = BANTUAN_PER_KK.get(status_siaga, 0)
    return int(affected_kk * bantuan), bantuan


def format_rupiah(amount):
    return "Rp{:,.0f}".format(amount).replace(",", ".")


# ==================================================
# DIAGNOSIS RULE-BASED
# Threshold curah hujan berdasarkan klasifikasi BMKG:
# - Hujan lebat      : 50-100mm / 24 jam
# - Hujan sangat lebat: >100mm / 24 jam
#
# Referensi:
# - BMKG (2021): Klasifikasi intensitas curah hujan
# - Jurnal Sylva Scienteae Vol.5 No.6 (2022): Analisis penyebab banjir
# ==================================================

def diagnose_flood_cause(feature_row, status_siaga):
    if status_siaga == "SIAGA 3":
        return "Kondisi aman atau normal."

    causes = []

    # Hujan lokal intensitas tinggi
    if feature_row["Rain_30min"] >= 10:
        causes.append("Hujan lokal intensitas tinggi (30 menit terakhir)")

    if feature_row["Rain_1h"] >= 20:
        causes.append("Hujan lokal lebat (1 jam terakhir)")

    if feature_row["Rain_3h"] >= 30:
        causes.append("Akumulasi hujan tinggi (3 jam terakhir)")

    if feature_row["Rain_6h"] >= 50:
        causes.append("Akumulasi hujan sangat tinggi (6 jam terakhir)")

    # Banjir kiriman dari hulu:
    # air naik cepat (WaterLevel_Change negatif = jarak mengecil = air naik)
    # tapi curah hujan lokal rendah
    is_kiriman = (
        feature_row["WaterLevel_Change_1h"] <= -0.15
        and feature_row["Rain_3h"] < 10
    )
    if is_kiriman:
        causes.append("Kemungkinan banjir kiriman dari hulu (air naik tanpa hujan lokal)")

    # Kenaikan permukaan air cepat
    if feature_row["WaterLevel_Change_30min"] <= -0.10:
        causes.append("Permukaan air naik cepat (30 menit terakhir)")

    if feature_row["WaterLevel_Change_3h"] <= -0.30:
        causes.append("Kenaikan permukaan air signifikan (3 jam terakhir)")

    # Tekanan udara rendah = cuaca buruk
    if feature_row["SeaLevelPressure_hPa"] <= 1005:
        causes.append("Tekanan udara rendah, indikasi cuaca buruk berlanjut")

    # Jarak sensor sangat dekat
    if feature_row["RiverWaterLevel_m"] <= 1.0:
        causes.append("Jarak sensor ke air sangat dekat, banjir terkonfirmasi")

    if not causes:
        causes.append(
            "Banjir terdeteksi model, penyebab dominan belum teridentifikasi dari sensor"
        )

    return " | ".join(causes)


# ==================================================
# BACA SENSOR (CSV STREAM)
# Membaca data sensor baris per baris dari CSV
# yang ditulis oleh gateway/perangkat sensor
# ==================================================

def read_sensor():
    global file_pointer

    df = pd.read_csv(CSV_SENSOR_PATH)

    if df.empty:
        return None

    if file_pointer >= len(df):
        return None

    row = df.iloc[file_pointer]
    file_pointer += 1

    return {
        "timestamp":  pd.to_datetime(row["waktu"]),
        "suhu":       float(row["suhu"]),
        "kelembapan": float(row["kelembapan"]),
        "tekanan":    float(row["tekanan"]),
        "jarak_air":  float(row["jarak_air"]),
        "rain_rate":  float(row["rain_rate"])
    }


# ==================================================
# KONVERSI SENSOR KE FORMAT MODEL
# ==================================================
# jarak_air (mm) dibagi 1000 -> distance_to_water_m
# Tidak dikonversi ke tinggi air — nilai mentah dipakai langsung
# karena threshold SIAGA berbasis jarak sensor ke air:
# makin kecil jarak = makin tinggi air = makin bahaya
# ==================================================

def convert_sensor_data(raw):
    distance_m = float(raw["jarak_air"]) / JARAK_AIR_DIVISOR

    return {
        "timestamp":            raw["timestamp"],
        "Temperature_C":        float(raw["suhu"]),
        "Humidity_percent":     float(raw["kelembapan"]),
        "SeaLevelPressure_hPa": float(raw["tekanan"]),
        "Precipitation_mm":     float(raw["rain_rate"]),
        "RiverWaterLevel_m":    float(distance_m)
    }


# ==================================================
# FEATURE ENGINEERING REALTIME
# ==================================================

def build_features(current_data):
    history.append(current_data)

    df_hist = pd.DataFrame(list(history))

    current_distance = current_data["RiverWaterLevel_m"]

    rain_30min = df_hist["Precipitation_mm"].tail(60).sum()
    rain_1h    = df_hist["Precipitation_mm"].tail(120).sum()
    rain_3h    = df_hist["Precipitation_mm"].tail(360).sum()
    rain_6h    = df_hist["Precipitation_mm"].tail(720).sum()

    def water_change(period):
        if len(df_hist) >= period:
            old_distance = df_hist["RiverWaterLevel_m"].iloc[-period]
            return current_distance - old_distance
        return 0.0

    feature_row = {
        "Temperature_C":        current_data["Temperature_C"],
        "Humidity_percent":     current_data["Humidity_percent"],
        "Precipitation_mm":     current_data["Precipitation_mm"],
        "SeaLevelPressure_hPa": current_data["SeaLevelPressure_hPa"],
        "RiverWaterLevel_m":    current_distance,

        "Rain_30min": rain_30min,
        "Rain_1h":    rain_1h,
        "Rain_3h":    rain_3h,
        "Rain_6h":    rain_6h,

        "WaterLevel_Change_30min": water_change(60),
        "WaterLevel_Change_1h":    water_change(120),
        "WaterLevel_Change_3h":    water_change(360)
    }

    X = pd.DataFrame([feature_row])

    missing_features = [f for f in features if f not in X.columns]
    if missing_features:
        raise ValueError(f"Feature kurang: {missing_features}")

    return X, feature_row


# ==================================================
# PREDIKSI RANDOM FOREST
# ==================================================

def predict_flood(X):
    X_model = X[features]

    rf_prob    = rf.predict_proba(X_model)[:, 1][0]
    final_prob = rf_prob

    pred_alert = int(final_prob >= threshold)

    return rf_prob, final_prob, pred_alert


# ==================================================
# LOGGING
# ==================================================

def save_log(result):
    file_exists = os.path.exists(LOG_PATH)

    log_row = pd.DataFrame([result])

    log_row.to_csv(
        LOG_PATH,
        mode="a",
        header=not file_exists,
        index=False
    )


# ==================================================
# ALERT ACTION
# ==================================================

def handle_alert(status_siaga, final_prob, distance_to_water_m):
    if status_siaga == "SIAGA 1":
        print("!!! FLOOD WARNING - DARURAT !!!")
        print("Status      :", status_siaga)
        print("Probability :", round(final_prob, 4))
        print("Jarak ke air:", round(distance_to_water_m, 3), "m")

    elif status_siaga == "SIAGA 2":
        print("!!! EARLY WARNING - WASPADA !!!")
        print("Status      :", status_siaga)
        print("Probability :", round(final_prob, 4))
        print("Jarak ke air:", round(distance_to_water_m, 3), "m")


# ==================================================
# MAIN LOOP
# ==================================================

print("Collecting initial history buffer...")

while True:
    try:
        raw_sensor = read_sensor()

        if raw_sensor is None:
            print("No new data")
            time.sleep(3)
            continue

        if raw_sensor["timestamp"] == last_timestamp:
            time.sleep(2)
            continue

        last_timestamp = raw_sensor["timestamp"]

        converted = convert_sensor_data(raw_sensor)

        X_input, feature_row = build_features(converted)

        if len(history) < MIN_HISTORY_FOR_PREDICTION:
            print(
                f"Collecting history... "
                f"{len(history)}/{MIN_HISTORY_FOR_PREDICTION}"
            )
            time.sleep(SENSOR_INTERVAL_SECONDS)
            continue

        rf_prob, final_prob, pred_alert = predict_flood(X_input)

        distance_to_water_m = converted["RiverWaterLevel_m"]
        status_siaga        = get_siaga_status(pred_alert, distance_to_water_m)
        is_flooded          = status_siaga in ("SIAGA 1", "SIAGA 2")

        # Estimasi dampak
        affected_area_ha             = estimate_affected_area_ha(status_siaga)
        affected_area_m2             = ha_to_m2(affected_area_ha)
        affected_kk                  = estimate_affected_kk(affected_area_ha)
        total_budget, bantuan_per_kk = estimate_budget(affected_kk, status_siaga)

        # Diagnosis penyebab
        diagnosis = diagnose_flood_cause(feature_row, status_siaga)

        result = {
            "timestamp":            converted["timestamp"],
            "distance_to_water_m":  distance_to_water_m,
            "rf_prob":              rf_prob,
            "final_prob":           final_prob,
            "threshold":            threshold,
            "pred_alert":           pred_alert,
            "status":               status_siaga,
            "is_flooded":           is_flooded,

            # Estimasi dampak
            "affected_area_ha":     affected_area_ha,
            "affected_area_m2":     affected_area_m2,
            "affected_kk":          affected_kk,
            "bantuan_per_kk_idr":   bantuan_per_kk,
            "total_budget_idr":     total_budget,

            # Sensor & features
            "Temperature_C":        feature_row["Temperature_C"],
            "Humidity_percent":     feature_row["Humidity_percent"],
            "Precipitation_mm":     feature_row["Precipitation_mm"],
            "SeaLevelPressure_hPa": feature_row["SeaLevelPressure_hPa"],

            "Rain_30min":              feature_row["Rain_30min"],
            "Rain_1h":                 feature_row["Rain_1h"],
            "Rain_3h":                 feature_row["Rain_3h"],
            "Rain_6h":                 feature_row["Rain_6h"],

            "WaterLevel_Change_30min": feature_row["WaterLevel_Change_30min"],
            "WaterLevel_Change_1h":    feature_row["WaterLevel_Change_1h"],
            "WaterLevel_Change_3h":    feature_row["WaterLevel_Change_3h"],

            "diagnosis": diagnosis
        }

        print("\n===================================")
        print("Timestamp           :", converted["timestamp"])
        print("Jarak Sensor ke Air :", round(distance_to_water_m, 3), "m")
        print("RF Probability      :", round(rf_prob, 4))
        print("Final Probability   :", round(final_prob, 4))
        print("Threshold           :", threshold)
        print("Prediction          :", pred_alert)
        print("Status              :", status_siaga)
        print("Banjir              :", is_flooded)
        print("-----------------------------------")
        print("Luas Terdampak      :", affected_area_ha, "Ha", f"({affected_area_m2} m²)")
        print("Estimasi KK         :", affected_kk, "KK")
        print("Bantuan per KK      :", format_rupiah(bantuan_per_kk))
        print("Total Dana Bantuan  :", format_rupiah(total_budget))
        print("-----------------------------------")
        print("Diagnosis           :", diagnosis)
        print("===================================")

        save_log(result)
        handle_alert(status_siaga, final_prob, distance_to_water_m)

        time.sleep(SENSOR_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("Program stopped by user.")
        break

    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)