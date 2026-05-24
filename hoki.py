#!/usr/bin/env python3

import time
import json
import datetime
import psycopg2
import pyrebase
import pandas as pd
from sqlalchemy import create_engine
import digitalio
import board
import busio
import adafruit_rfm9x
import re
import os
import math
import joblib
from collections import deque
import numpy as np  # Tambahkan import numpy
import psutil       # TAMBAHAN: Untuk monitoring CPU dan Memory Gateway

# ===============================================================
# FUNGSI KONVERSI NUMPY KE NATIVE PYTHON
# ===============================================================
def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON/DB storage"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    return obj

# ===============================================================
# PREDIKSI & ANALISIS BANJIR (Dari Code Kedua)
# ===============================================================

# ==================================================
# CONFIG PREDIKSI
# ==================================================

MODEL_PATH = "flood_early_warning_rf_model.pkl"
PREDICTION_LOG_PATH = "flood_prediction_log.csv"

# 30 detik interval untuk prediksi (sama dengan interval sensor)
SENSOR_INTERVAL_SECONDS = 30

# 30 detik interval:
# 30 menit = 60 data
# 1 jam    = 120 data
# 3 jam    = 360 data
# 6 jam    = 720 data
MIN_HISTORY_FOR_PREDICTION = 60
MAX_HISTORY = 720

# jarak_air dari sensor/gateway dalam meter
JARAK_AIR_DIVISOR = 100.0

# ==================================================
# RULE-BASED CONFIG
# ==================================================

# Luas total wilayah RT dalam Ha
TOTAL_AREA_HA = 6.0

# Jumlah KK total di RT
TOTAL_KK = 35

# Kepadatan KK per Ha
KK_PER_HA = TOTAL_KK / TOTAL_AREA_HA

# Persentase luas terdampak per siaga
SIAGA_3_DAMPAK_PERSEN = 0.20
SIAGA_2_DAMPAK_PERSEN = 0.45
SIAGA_1_DAMPAK_PERSEN = 0.70

# Bantuan per KK per siaga
BANTUAN_PER_KK = {
    "SIAGA 3": 350_000,
    "SIAGA 2": 650_000,
    "SIAGA 1": 1_000_000,
}

# ==================================================
# LOAD MODEL
# ==================================================

rf = None
features = []
threshold = 0.5
model_loaded = False

if os.path.exists(MODEL_PATH):
    try:
        model_data = joblib.load(MODEL_PATH)
        rf = model_data["rf"]
        features = model_data["features"]
        threshold = float(model_data["threshold"])  # Konversi ke float
        model_loaded = True
        print("✅ Random Forest Model Loaded Successfully")
        print(f"   Threshold : {threshold}")
        print(f"   Features  : {features}")
    except Exception as e:
        print(f"⚠️ Model loading error: {e}")
        print("   Running in rule-based mode only")
else:
    print(f"⚠️ Model not found at {MODEL_PATH}")
    print("   Running in rule-based mode only")

# ==================================================
# HISTORY BUFFER UNTUK PREDIKSI
# ==================================================

history = deque(maxlen=MAX_HISTORY)
last_prediction_time = None

# ==================================================
# FUNGSI PREDIKSI
# ==================================================

def get_siaga_status(pred_alert, distance_to_water_m):
    """Menentukan status siaga berdasarkan prediksi dan jarak air"""
    # Konversi ke tipe native
    pred_alert = int(pred_alert) if not isinstance(pred_alert, int) else pred_alert
    distance_to_water_m = float(distance_to_water_m)
    
    if pred_alert == 0:
        return "SIAGA 3"
    
    if distance_to_water_m <= 1.0:
        return "SIAGA 1"
    
    if distance_to_water_m <= 1.3:
        return "SIAGA 2"
    
    return "SIAGA 3"

def estimate_affected_area_ha(status_siaga):
    """Luas terdampak dalam Ha berdasarkan status siaga"""
    if status_siaga == "SIAGA 1":
        persen = SIAGA_1_DAMPAK_PERSEN
    elif status_siaga == "SIAGA 2":
        persen = SIAGA_2_DAMPAK_PERSEN
    else:
        persen = SIAGA_3_DAMPAK_PERSEN
    
    return round(float(persen * TOTAL_AREA_HA), 2)

def ha_to_m2(ha):
    return int(float(ha) * 10_000)

def estimate_affected_kk(area_ha):
    """Estimasi KK terdampak dari luas area"""
    kk = float(area_ha) * KK_PER_HA
    return min(int(round(kk)), TOTAL_KK)

def estimate_budget(affected_kk, status_siaga):
    """Total dana bantuan = KK terdampak x bantuan per KK sesuai siaga"""
    bantuan = BANTUAN_PER_KK.get(status_siaga, 0)
    return int(int(affected_kk) * bantuan), int(bantuan)

def format_rupiah(amount):
    return "Rp{:,.0f}".format(int(amount)).replace(",", ".")

def diagnose_flood_cause(feature_row, status_siaga):
    """Diagnosis penyebab banjir berdasarkan data sensor"""
    if status_siaga == "SIAGA 3":
        return "Kondisi aman atau normal."
    
    causes = []
    
    # Hujan lokal intensitas tinggi
    if float(feature_row.get("Rain_30min", 0)) >= 10:
        causes.append("Hujan lokal intensitas tinggi (30 menit terakhir)")
    
    if float(feature_row.get("Rain_1h", 0)) >= 20:
        causes.append("Hujan lokal lebat (1 jam terakhir)")
    
    if float(feature_row.get("Rain_3h", 0)) >= 30:
        causes.append("Akumulasi hujan tinggi (3 jam terakhir)")
    
    if float(feature_row.get("Rain_6h", 0)) >= 50:
        causes.append("Akumulasi hujan sangat tinggi (6 jam terakhir)")
    
    # Banjir kiriman dari hulu
    is_kiriman = (
        float(feature_row.get("WaterLevel_Change_1h", 0)) <= -0.15
        and float(feature_row.get("Rain_3h", 0)) < 10
    )
    if is_kiriman:
        causes.append("Kemungkinan banjir kiriman dari hulu")
    
    # Kenaikan permukaan air cepat
    if float(feature_row.get("WaterLevel_Change_30min", 0)) <= -0.10:
        causes.append("Permukaan air naik cepat (30 menit terakhir)")
    
    if float(feature_row.get("WaterLevel_Change_3h", 0)) <= -0.30:
        causes.append("Kenaikan permukaan air signifikan (3 jam terakhir)")
    
    # Tekanan udara rendah
    if float(feature_row.get("SeaLevelPressure_hPa", 1013)) <= 1005:
        causes.append("Tekanan udara rendah, indikasi cuaca buruk")
    
    # Jarak sensor sangat dekat
    if float(feature_row.get("RiverWaterLevel_m", 10)) <= 1.0:
        causes.append("Jarak sensor ke air sangat dekat, banjir terkonfirmasi")
    
    if not causes:
        causes.append("Banjir terdeteksi, penyebab dominan belum teridentifikasi")
    
    return " | ".join(causes)

def convert_sensor_data_for_prediction(raw_data):
    """Konversi data sensor ke format untuk prediksi"""
    jarak_air = raw_data.get("jarak_air", 0)
    if jarak_air is None:
        jarak_air = 0
    distance_m = float(jarak_air) / JARAK_AIR_DIVISOR
    
    return {
        "timestamp":            datetime.datetime.now(),
        "Temperature_C":        float(raw_data.get("suhu", 0) or 0),
        "Humidity_percent":     float(raw_data.get("kelembapan", 0) or 0),
        "SeaLevelPressure_hPa": float(raw_data.get("tekanan", 1013) or 1013),
        "Precipitation_mm":     float(raw_data.get("rain_rate", 0) or 0),
        "RiverWaterLevel_m":    float(distance_m)
    }

def build_features_for_prediction(current_data):
    """Membangun fitur untuk prediksi berdasarkan history"""
    history.append(current_data)
    
    df_hist = pd.DataFrame(list(history))
    
    current_distance = float(current_data["RiverWaterLevel_m"])
    current_precipitation = float(current_data["Precipitation_mm"])
    
    # Hitung akumulasi hujan dengan konversi ke float
    if len(df_hist) >= 60:
        rain_30min = float(df_hist["Precipitation_mm"].tail(60).sum())
    else:
        rain_30min = current_precipitation * 60
    
    if len(df_hist) >= 120:
        rain_1h = float(df_hist["Precipitation_mm"].tail(120).sum())
    else:
        rain_1h = current_precipitation * 120
    
    if len(df_hist) >= 360:
        rain_3h = float(df_hist["Precipitation_mm"].tail(360).sum())
    else:
        rain_3h = current_precipitation * 360
    
    if len(df_hist) >= 720:
        rain_6h = float(df_hist["Precipitation_mm"].tail(720).sum())
    else:
        rain_6h = current_precipitation * 720
    
    def water_change(period):
        if len(df_hist) >= period:
            old_distance = float(df_hist["RiverWaterLevel_m"].iloc[-period])
            return float(current_distance - old_distance)
        return 0.0
    
    feature_row = {
        "Temperature_C":        float(current_data["Temperature_C"]),
        "Humidity_percent":     float(current_data["Humidity_percent"]),
        "Precipitation_mm":     float(current_data["Precipitation_mm"]),
        "SeaLevelPressure_hPa": float(current_data["SeaLevelPressure_hPa"]),
        "RiverWaterLevel_m":    float(current_distance),
        "Rain_30min":           float(rain_30min),
        "Rain_1h":              float(rain_1h),
        "Rain_3h":              float(rain_3h),
        "Rain_6h":              float(rain_6h),
        "WaterLevel_Change_30min": float(water_change(60)),
        "WaterLevel_Change_1h":    float(water_change(120)),
        "WaterLevel_Change_3h":    float(water_change(360))
    }
    
    return feature_row

def predict_flood(feature_row):
    """Prediksi banjir menggunakan Random Forest (jika tersedia)"""
    if not model_loaded or rf is None:
        # Rule-based prediction jika model tidak tersedia
        jarak = float(feature_row.get("RiverWaterLevel_m", 10))
        if jarak <= 0.5:
            return 0.95, 0.95, 1
        elif jarak <= 1.0:
            return 0.7, 0.7, 1
        elif jarak <= 1.3:
            return 0.4, 0.4, 0
        else:
            return 0.1, 0.1, 0
    
    try:
        # Buat DataFrame dengan fitur yang sesuai
        X = pd.DataFrame([feature_row])
        X_model = X[features]
        rf_prob = float(rf.predict_proba(X_model)[:, 1][0])  # Konversi ke float
        final_prob = float(rf_prob)
        pred_alert = int(final_prob >= threshold)
        return rf_prob, final_prob, pred_alert
    except Exception as e:
        print(f"⚠️ Prediction error: {e}")
        return 0.0, 0.0, 0

def save_prediction_log(result):
    """Menyimpan hasil prediksi ke CSV"""
    # Konversi semua numpy types
    result = convert_numpy_types(result)
    
    file_exists = os.path.exists(PREDICTION_LOG_PATH)
    log_row = pd.DataFrame([result])
    log_row.to_csv(PREDICTION_LOG_PATH, mode="a", header=not file_exists, index=False)

# ===============================================================
# POSTGRESQL
# ===============================================================
conn = psycopg2.connect(
    host="localhost",
    database="ews_banjir",
    user="pi",
    password="ews"
)
cur = conn.cursor()
engine = create_engine("postgresql+psycopg2://pi:ews@localhost/ews_banjir")
print("✅ PostgreSQL Connected")

# ===============================================================
# AUTO CREATE TABLE
# ===============================================================
# TAMBAHAN: Kolom 'gateway_cpu' dan 'gateway_ram' ditambahkan ke schema tabel awal
cur.execute("""
CREATE TABLE IF NOT EXISTS sensor_log (
    id SERIAL PRIMARY KEY,
    waktu TIMESTAMP,
    suhu REAL,
    kelembapan REAL,
    tekanan REAL,
    jarak_air REAL,
    flow REAL,
    rain_total REAL,
    rain_rate REAL,
    float_level REAL,
    alert VARCHAR(50),
    seq INTEGER,
    rssi INTEGER,
    gateway_cpu REAL,
    gateway_ram REAL
)
""")
conn.commit()

# Proteksi migrasi: Tambahkan kolom baru ke DB jika tabel lama sudah terlanjur ada tanpa kolom ini
for col in [('gateway_cpu', 'REAL'), ('gateway_ram', 'REAL')]:
    try:
        cur.execute(f"ALTER TABLE sensor_log ADD COLUMN {col[0]} {col[1]};")
        conn.commit()
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()

# Tambahan tabel untuk prediksi jika belum ada
cur.execute("""
CREATE TABLE IF NOT EXISTS flood_prediction (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    distance_to_water_m REAL,
    rf_prob REAL,
    final_prob REAL,
    threshold REAL,
    pred_alert INTEGER,
    status VARCHAR(20),
    is_flooded BOOLEAN,
    affected_area_ha REAL,
    affected_area_m2 INTEGER,
    affected_kk INTEGER,
    bantuan_per_kk_idr BIGINT,
    total_budget_idr BIGINT,
    diagnosis TEXT,
    suhu REAL,
    kelembapan REAL,
    tekanan REAL,
    rain_rate REAL,
    rain_30min REAL,
    rain_1h REAL,
    rain_3h REAL,
    rain_6h REAL,
    water_level_change_30min REAL,
    water_level_change_1h REAL,
    water_level_change_3h REAL
)
""")
conn.commit()
print("🛢 Tables Ready")

# ===============================================================
# FIREBASE
# ===============================================================
config = {
    "apiKey": "AIzaSyBmgepsmVXP1ekfUl47RsllWl-BnjKkSno",
    "authDomain": "ews3-858da.firebaseapp.com",
    "databaseURL": "https://ews3-858da-default-rtdb.asia-southeast1.firebasedatabase.app/",
    "storageBucket": "ews3-858da.appspot.com"
}
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()
EMAIL = "ewsraspy@gmail.com"
PASSWORD = "ewskelompok3"

try:
    firebase_user = auth.sign_in_with_email_and_password(EMAIL, PASSWORD)
    token = firebase_user["idToken"]
    UID = firebase_user["localId"]
    print("🔥 Firebase Login Success")
except Exception as e:
    print("❌ Firebase Login Error:", e)
    exit()

# ===============================================================
# CONFIG
# ===============================================================
FREQ = 915.0
TOTAL_PACKET = 0
LAST_WAIT_PRINT = 0
CSV_EXPORT_INTERVAL = 60
LAST_CSV_EXPORT = 0

# ===============================================================
# CACHE DATA TERAKHIR
# ===============================================================
LAST_COMPLETE_DATA = {}
LAST_PREDICTION_RESULT = None

# ===============================================================
# INIT LORA
# ===============================================================
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.D4)
reset = digitalio.DigitalInOut(board.D25)
rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, FREQ)
rfm9x.tx_power = 13
rfm9x.signal_bandwidth = 125000
rfm9x.coding_rate = 5
rfm9x.spreading_factor = 10
rfm9x.enable_crc = True
print("✅ LoRa Aktif")
print("-" * 70)

# ===============================================================
# SMART PARSER
# ===============================================================
def parse_packet(raw):
    raw = raw.strip()
    if not raw:
        return None
    
    if raw.startswith('":'):
        raw = raw[3:]
        if not raw.startswith('{'):
            raw = '{' + raw
    
    if raw.startswith(':'):
        raw = '{"t"' + raw
    
    if not raw.startswith('{'):
        raw = '{' + raw
    
    if not raw.endswith('}'):
        raw += '}'
    
    raw = re.sub(r'([a-zA-Z]+):', r'"\1":', raw)
    raw = raw.replace("'", '"')
    raw = re.sub(r'[^\x20-\x7E]', '', raw)
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = {}
            pairs = re.findall(r'"?([a-zA-Z]+)"?\s*:\s*([0-9.]+)', raw)
            for key, value in pairs:
                if '.' in value:
                    data[key] = float(value)
                else:
                    data[key] = int(value)
            return data if data else None
        except:
            return None

# ===============================================================
# MERGE PARTIAL DATA
# ===============================================================
def merge_with_last_data(data):
    global LAST_COMPLETE_DATA
    important_keys = ['t', 'h', 'p', 'd']
    is_complete = any(k in data for k in important_keys)
    
    if is_complete:
        LAST_COMPLETE_DATA.update(data)

        # Konversi jarak air dari mm ke cm
        if 'd' in LAST_COMPLETE_DATA:
            LAST_COMPLETE_DATA['d'] = round(float(LAST_COMPLETE_DATA['d']) / 10, 1)

        return LAST_COMPLETE_DATA.copy()
    else:
        merged = LAST_COMPLETE_DATA.copy()
        merged.update(data)
        return merged

# ===============================================================
# UPDATE FIREBASE DENGAN PREDIKSI & METRIK GATEWAY
# ===============================================================
def update_firebase_with_prediction(sensor_data, prediction_result, rssi):
    """Update Firebase dengan data sensor, prediksi, dan performa internal gateway"""
    try:
        # Format timestamp
        current_time = datetime.datetime.now()
        timestamp_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Konversi semua nilai ke tipe native
        sensor_data = convert_numpy_types(sensor_data)
        prediction_result = convert_numpy_types(prediction_result or {})
        
        # TAMBAHAN: Mengambil metrik performa internal gateway secara real-time
        gateway_cpu = psutil.cpu_percent(interval=None)
        gateway_ram = psutil.virtual_memory().percent
        
        # Data yang akan dikirim ke Firebase
        payload = {
            "timestamp": timestamp_str,
            "suhu": float(sensor_data.get('t', 0) or 0),
            "kelembapan": float(sensor_data.get('h', 0) or 0),
            "tekanan": float(sensor_data.get('p', 0) or 0),
            "jarak_air": float(sensor_data.get('d', 0) or 0),
            "flow": float(sensor_data.get('f', 0) or 0),
            "rain_total": float(sensor_data.get('rt', 0) or 0),
            "rain_rate": float(sensor_data.get('rr', 0) or 0),
            "float_level": float(sensor_data.get('lv', 0) or 0),
            "alert": str(sensor_data.get('al', 'NORMAL')),
            "seq": int(sensor_data.get('sq', 0) or 0),
            "rssi": int(rssi),
            "status": "Monitoring",
            
            # TAMBAHAN PERFORMA GATEWAY (FCAPS Accounting Management)
            "gateway_cpu": float(gateway_cpu),
            "gateway_ram": float(gateway_ram),
            
            # Tambahan data prediksi
            "prediction_status": str(prediction_result.get("status", "SIAGA 3")),
            "is_flooded": bool(prediction_result.get("is_flooded", False)),
            "probability": float(prediction_result.get("final_prob", 0)),
            "distance_to_water_m": float(prediction_result.get("distance_to_water_m", 0)),
            "affected_area_ha": float(prediction_result.get("affected_area_ha", 0)),
            "affected_kk": int(prediction_result.get("affected_kk", 0)),
            "total_budget_idr": int(prediction_result.get("total_budget_idr", 0)),
            "diagnosis": str(prediction_result.get("diagnosis", ""))
        }
        
        # Update ke Firebase di node "latest"
        db.child("node1").child("latest").child(UID).set(payload, token)
        
        # Simpan ke history
        db.child("node1").child("history").child(UID).push(payload, token)
        
        print("☁️ Firebase Updated with Prediction & Gateway Metrics")
        
    except Exception as e:
        print(f"❌ Firebase Update Error: {e}")

# ===============================================================
# PROSES PREDIKSI
# ===============================================================
def process_prediction(sensor_dict, rssi):
    """Proses prediksi berdasarkan data sensor terbaru"""
    global last_prediction_time, history
    
    current_time = datetime.datetime.now()
    
    # Cek apakah sudah waktunya prediksi (setiap 30 detik)
    if last_prediction_time is not None:
        time_diff = (current_time - last_prediction_time).total_seconds()
        if time_diff < SENSOR_INTERVAL_SECONDS:
            return None
    
    # Konversi data sensor untuk prediksi
    converted = convert_sensor_data_for_prediction(sensor_dict)
    
    # Build features
    feature_row = build_features_for_prediction(converted)
    
    # Cek apakah history sudah cukup
    if len(history) < MIN_HISTORY_FOR_PREDICTION:
        print(f"📊 Collecting history for prediction... {len(history)}/{MIN_HISTORY_FOR_PREDICTION}")
        return None
    
    # Prediksi
    rf_prob, final_prob, pred_alert = predict_flood(feature_row)
    distance_to_water_m = float(converted["RiverWaterLevel_m"])
    status_siaga = get_siaga_status(pred_alert, distance_to_water_m)
    is_flooded = status_siaga in ("SIAGA 1", "SIAGA 2")
    
    # Estimasi dampak
    affected_area_ha = estimate_affected_area_ha(status_siaga)
    affected_area_m2 = ha_to_m2(affected_area_ha)
    affected_kk = estimate_affected_kk(affected_area_ha)
    total_budget, bantuan_per_kk = estimate_budget(affected_kk, status_siaga)
    
    # Diagnosis
    diagnosis = diagnose_flood_cause(feature_row, status_siaga)
    
    # Hasil prediksi - semua nilai dipastikan tipe native Python
    prediction_result = {
        "timestamp": converted["timestamp"],
        "distance_to_water_m": float(distance_to_water_m),
        "rf_prob": float(rf_prob),
        "final_prob": float(final_prob),
        "threshold": float(threshold),
        "pred_alert": int(pred_alert),
        "status": str(status_siaga),
        "is_flooded": bool(is_flooded),
        "affected_area_ha": float(affected_area_ha),
        "affected_area_m2": int(affected_area_m2),
        "affected_kk": int(affected_kk),
        "bantuan_per_kk_idr": int(bantuan_per_kk),
        "total_budget_idr": int(total_budget),
        "diagnosis": str(diagnosis),
        "suhu": float(feature_row["Temperature_C"]),
        "kelembapan": float(feature_row["Humidity_percent"]),
        "tekanan": float(feature_row["SeaLevelPressure_hPa"]),
        "rain_rate": float(feature_row["Precipitation_mm"]),
        "rain_30min": float(feature_row["Rain_30min"]),
        "rain_1h": float(feature_row["Rain_1h"]),
        "rain_3h": float(feature_row["Rain_3h"]),
        "rain_6h": float(feature_row["Rain_6h"]),
        "water_level_change_30min": float(feature_row["WaterLevel_Change_30min"]),
        "water_level_change_1h": float(feature_row["WaterLevel_Change_1h"]),
        "water_level_change_3h": float(feature_row["WaterLevel_Change_3h"])
    }
    
    # Tampilkan hasil prediksi
    print("\n" + "=" * 50)
    print("🔮 FLOOD PREDICTION RESULT")
    print("=" * 50)
    print(f"📊 Status Siaga    : {status_siaga}")
    print(f"🌊 Jarak ke Air    : {round(distance_to_water_m, 3)} m")
    print(f"📈 Probabilitas    : {round(final_prob * 100, 2)}%")
    print(f"🏠 Luas Terdampak  : {affected_area_ha} Ha ({affected_area_m2} m²)")
    print(f"👨‍👩‍👧‍👦 KK Terdampak    : {affected_kk} KK")
    print(f"💰 Total Bantuan   : {format_rupiah(total_budget)}")
    print(f"📋 Diagnosis       : {diagnosis}")
    print("=" * 50)
    
    # Simpan ke database - pastikan semua nilai sudah tipe native
    try:
        cur.execute("""
        INSERT INTO flood_prediction (
            timestamp, distance_to_water_m, rf_prob, final_prob, threshold,
            pred_alert, status, is_flooded, affected_area_ha, affected_area_m2,
            affected_kk, bantuan_per_kk_idr, total_budget_idr, diagnosis,
            suhu, kelembapan, tekanan, rain_rate, rain_30min, rain_1h,
            rain_3h, rain_6h, water_level_change_30min, water_level_change_1h,
            water_level_change_3h
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            prediction_result["timestamp"],
            prediction_result["distance_to_water_m"],
            prediction_result["rf_prob"],
            prediction_result["final_prob"],
            prediction_result["threshold"],
            prediction_result["pred_alert"],
            prediction_result["status"],
            prediction_result["is_flooded"],
            prediction_result["affected_area_ha"],
            prediction_result["affected_area_m2"],
            prediction_result["affected_kk"],
            prediction_result["bantuan_per_kk_idr"],
            prediction_result["total_budget_idr"],
            prediction_result["diagnosis"],
            prediction_result["suhu"],
            prediction_result["kelembapan"],
            prediction_result["tekanan"],
            prediction_result["rain_rate"],
            prediction_result["rain_30min"],
            prediction_result["rain_1h"],
            prediction_result["rain_3h"],
            prediction_result["rain_6h"],
            prediction_result["water_level_change_30min"],
            prediction_result["water_level_change_1h"],
            prediction_result["water_level_change_3h"]
        ))
        conn.commit()
        print("🛢 Prediction saved to PostgreSQL")
    except Exception as e:
        print(f"❌ DB Save Error: {e}")
        conn.rollback()
    
    # Simpan ke log CSV
    save_prediction_log(prediction_result)
    
    # Tampilkan alert jika siaga
    if status_siaga == "SIAGA 1":
        print("\n🔴🔴🔴 FLOOD WARNING - DARURAT! 🔴🔴🔴")
        print("🚨 SEGERA EVAKUASI! 🚨")
    elif status_siaga == "SIAGA 2":
        print("\n🟠🟠🟠 EARLY WARNING - WASPADA! 🟠🟠🟠")
        print("⚠️ PERSIAPKAN EVAKUASI! ⚠️")
    
    last_prediction_time = current_time
    return prediction_result

# ===============================================================
# DISPLAY
# ===============================================================
def tampilkan_data(data, rssi):
    global TOTAL_PACKET
    TOTAL_PACKET += 1
    
    # Ambil data performa untuk ditampilkan di terminal
    g_cpu = psutil.cpu_percent(interval=None)
    g_ram = psutil.virtual_memory().percent
    
    print("\n" + "═" * 70)
    print(f"📩 DATA #{TOTAL_PACKET}")
    print(f"🕒 Waktu : {datetime.datetime.now().strftime('%H:%M:%S')}")
    print(f"📶 RSSI  : {rssi} dBm")
    print(f"💻 GW CPU: {g_cpu}% | GW RAM: {g_ram}%") # Cetak spek resource di terminal
    print(f"🌡️ Suhu  : {data.get('t', 'N/A')}")
    print(f"💧 Hum   : {data.get('h', 'N/A')}")
    print(f"🎯 Tekanan: {data.get('p', 'N/A')}")
    print(f"🌊 Level : {data.get('d', 'N/A')} cm")
    print(f"💧 Float : {data.get('lv', 'N/A')}")
    print(f"⚠️ Alert : {data.get('al', 'NORMAL')}")
    print(f"🔢 Seq   : {data.get('sq', 'N/A')}")
    print("═" * 70)

# ===============================================================
# SAVE POSTGRESQL WITH GATEWAY METRICS
# ===============================================================
def simpan_postgresql(data, rssi):
    try:
        # TAMBAHAN: Ambil kapasitas kerja server lokal saat data LoRa masuk
        g_cpu = psutil.cpu_percent(interval=None)
        g_ram = psutil.virtual_memory().percent

        cur.execute("""
        INSERT INTO sensor_log (
            waktu, suhu, kelembapan, tekanan, jarak_air,
            flow, rain_total, rain_rate, float_level, alert, seq, rssi,
            gateway_cpu, gateway_ram
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            datetime.datetime.now(),
            float(data.get('t', 0) or 0),
            float(data.get('h', 0) or 0),
            float(data.get('p', 0) or 0),
            float(data.get('d', 0) or 0),
            float(data.get('f', 0) or 0),
            float(data.get('rt', 0) or 0),
            float(data.get('rr', 0) or 0),
            float(data.get('lv', 0) or 0),
            str(data.get('al', 'NORMAL')),
            int(data.get('sq', 0) or 0),
            int(rssi),
            float(g_cpu),  # TAMBAHAN: Simpan ke DB lokal
            float(g_ram)   # TAMBAHAN: Simpan ke DB lokal
        ))
        conn.commit()
        print("🛢 PostgreSQL OK")
    except Exception as e:
        print(f"❌ PostgreSQL ERROR: {e}")
        conn.rollback()

# ===============================================================
# EXPORT CSV
# ===============================================================
def export_csv():
    try:
        query = "SELECT * FROM sensor_log ORDER BY id DESC LIMIT 1000"
        df = pd.read_sql(query, engine)
        df.to_csv("sensor_data.csv", index=False)
        print("📁 CSV Export Updated")
    except Exception as e:
        print(f"❌ CSV EXPORT ERROR: {e}")

# ===============================================================
# LIVE RSSI (Noise floor monitoring)
# ===============================================================
def get_live_rssi():
    try:
        raw = rfm9x._read_u8(0x1B)
        return raw - 157
    except:
        return -999

def noise_label(v):
    if v <= -115:
        return "🟢 Bersih"
    elif v <= -105:
        return "🟡 Normal"
    elif v <= -95:
        return "🟠 Sedikit Noise"
    else:
        return "🔴 Bising"

# ===============================================================
# MAIN LOOP
# ===============================================================
print("📡 Receiver Ready with Flood Prediction & Management Monitoring")
print("-" * 70)

while True:
    try:
        packet = rfm9x.receive(timeout=1.0)
        
        if packet is not None:
            raw_str = packet.decode("utf-8", errors="ignore")
            data = parse_packet(raw_str)
            
            if data and len(data) > 0:
                rssi = rfm9x.last_rssi
                
                # Merge data dengan data terakhir
                final_data = merge_with_last_data(data)
                
                # Simpan ke database (Sekaligus mencatat CPU & RAM)
                simpan_postgresql(final_data, rssi)
                
                # Proses prediksi banjir
                prediction_result = process_prediction(final_data, rssi)
                
                # Update Firebase dengan data sensor, prediksi, DAN metrik performa gateway
                update_firebase_with_prediction(final_data, prediction_result or {}, rssi)
                
                # Tampilkan data
                tampilkan_data(final_data, rssi)
                
            else:
                print("❌ Gagal parse packet")
        else:
            now = time.time()
            if now - LAST_WAIT_PRINT >= 2:
                noise = get_live_rssi()
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                      f"⌛ Waiting... | Noise: {noise} dBm | {noise_label(noise)}")
                LAST_WAIT_PRINT = now
            
            if now - LAST_CSV_EXPORT >= CSV_EXPORT_INTERVAL:
                export_csv()
                LAST_CSV_EXPORT = now
                
    except KeyboardInterrupt:
        print("\n🛑 STOP")
        break
    except Exception as e:
        print(f"❌ ERROR: {e}")
        time.sleep(1)

cur.close()
conn.close()
print("✅ Connections closed")