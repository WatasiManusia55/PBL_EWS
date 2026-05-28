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
import numpy as np
import psutil  # Untuk monitoring sistem (CPU/Mem/Disk/Pi temp)

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
# FUNGSI MONITORING SISTEM
# ===============================================================
def get_system_metrics():
    """Mendapatkan metrik sistem: CPU, Memory, Disk, Load Avg, Pi Temperature"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)

        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)

        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)

        load_avg = psutil.getloadavg()

        # Temperature (Raspberry Pi thermal zone)
        temp_celsius = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_celsius = float(f.read().strip()) / 1000.0
        except:
            pass

        return {
            "cpu_percent":          round(cpu_percent, 1),
            "memory_percent":       round(memory_percent, 1),
            "memory_used_mb":       round(memory_used_mb, 1),
            "memory_total_mb":      round(memory_total_mb, 1),
            "disk_percent":         round(disk_percent, 1),
            "disk_used_gb":         round(disk_used_gb, 1),
            "disk_total_gb":        round(disk_total_gb, 1),
            "load_avg_1min":        round(load_avg[0], 2),
            "load_avg_5min":        round(load_avg[1], 2),
            "load_avg_15min":       round(load_avg[2], 2),
            "temperature_celsius":  temp_celsius
        }
    except Exception as e:
        print(f"⚠️ Error getting system metrics: {e}")
        return {
            "cpu_percent": 0, "memory_percent": 0,
            "memory_used_mb": 0, "memory_total_mb": 0,
            "disk_percent": 0, "disk_used_gb": 0, "disk_total_gb": 0,
            "load_avg_1min": 0, "load_avg_5min": 0, "load_avg_15min": 0,
            "temperature_celsius": None
        }

def get_live_rssi():
    """Live RSSI dari register LoRa (tanpa nunggu paket)"""
    try:
        raw = rfm9x._read_u8(0x1B)
        return raw - 157
    except:
        return -999

def noise_label(v):
    """Label noise berdasarkan nilai RSSI (text only, untuk DB)"""
    if v <= -115:
        return "Bersih"
    elif v <= -105:
        return "Normal"
    elif v <= -95:
        return "Sedikit Noise"
    else:
        return "Bising"

# ===============================================================
# CONFIG PREDIKSI & ANALISIS BANJIR
# ===============================================================

MODEL_PATH = "flood_early_warning_rf_model.pkl"
PREDICTION_LOG_PATH = "flood_prediction_log.csv"

# Interval prediksi (sama dengan interval kirim sensor)
SENSOR_INTERVAL_SECONDS = 30

# History buffer (interval 30 detik):
# 30 menit = 60 data
# 1 jam    = 120 data
# 3 jam    = 360 data
# 6 jam    = 720 data
MIN_HISTORY_FOR_PREDICTION = 60
MAX_HISTORY = 720

# ----------------------------------------------------------------
# KONVERSI SATUAN JARAK AIR
# ----------------------------------------------------------------
CM_TO_M_DIVISOR = 100.0

# ----------------------------------------------------------------
# KONFIGURASI FISIK SENSOR
# ----------------------------------------------------------------

THRESHOLD_SIAGA_1_M = 1.20  # Air tumpah ke jalan (DARURAT)
THRESHOLD_SIAGA_2_M = 1.40  # Mendekati tumpah (WASPADA)
# SIAGA 3 = default state (pemantauan rutin / aman)

JARAK_DASAR_SUNGAI_M = 3.0

# ==================================================
# RULE-BASED CONFIG (Estimasi Dampak)
# ==================================================

TOTAL_AREA_HA = 6.0                 # Luas total RT (Ha)
TOTAL_KK = 35                       # Jumlah KK total
KK_PER_HA = TOTAL_KK / TOTAL_AREA_HA

# Persentase luas terdampak per siaga
# SIAGA 3 = aman, tidak ada dampak (0%)
SIAGA_2_DAMPAK_PERSEN = 0.45
SIAGA_1_DAMPAK_PERSEN = 0.70

# Bantuan per KK per siaga (IDR) — SIAGA 3 = aman, tidak ada bantuan
BANTUAN_PER_KK = {
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
        threshold = float(model_data["threshold"])
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
# FUNGSI PREDIKSI & STATUS
# ==================================================

def get_siaga_status(pred_alert, distance_to_water_m):
    """
    Tentukan status siaga gabungan: physical thresholds + ML early warning.

    Urutan prioritas:
      1. Fisik darurat/waspada:
         - distance <= 1.20m → SIAGA 1 (darurat fisik)
         - distance <= 1.40m → SIAGA 2 (waspada fisik)
      2. ML early warning:
         - Fisik aman tapi ML deteksi pola berbahaya (pred_alert=1) → SIAGA 2
      3. Default → SIAGA 3 (pemantauan rutin / aman)
    """
    pred_alert = int(pred_alert) if not isinstance(pred_alert, int) else pred_alert
    distance_to_water_m = float(distance_to_water_m)

    # 1. Fisik darurat/waspada
    if distance_to_water_m <= THRESHOLD_SIAGA_1_M:
        return "SIAGA 1"
    if distance_to_water_m <= THRESHOLD_SIAGA_2_M:
        return "SIAGA 2"

    # 2. ML early warning (fisik masih aman tapi pola sensor mengkhawatirkan)
    if pred_alert == 1:
        return "SIAGA 2"

    # 3. Default: pemantauan rutin
    return "SIAGA 3"

def estimate_affected_area_ha(status_siaga):
    """Luas terdampak dalam Ha berdasarkan status siaga."""
    if status_siaga == "SIAGA 1":
        persen = SIAGA_1_DAMPAK_PERSEN
    elif status_siaga == "SIAGA 2":
        persen = SIAGA_2_DAMPAK_PERSEN
    else:
        # SIAGA 3 (pemantauan rutin / aman) → tidak ada area terdampak
        persen = 0.0
    return round(float(persen * TOTAL_AREA_HA), 2)

def ha_to_m2(ha):
    return int(float(ha) * 10_000)

def estimate_affected_kk(area_ha):
    kk = float(area_ha) * KK_PER_HA
    return min(int(round(kk)), TOTAL_KK)

def estimate_budget(affected_kk, status_siaga):
    """Total dana bantuan = KK terdampak x bantuan per KK sesuai siaga.
    SIAGA 3 atau status tak dikenal -> 0 (via dict default)."""
    bantuan = BANTUAN_PER_KK.get(status_siaga, 0)
    return int(int(affected_kk) * bantuan), int(bantuan)

def format_rupiah(amount):
    return "Rp{:,.0f}".format(int(amount)).replace(",", ".")

def diagnose_flood_cause(feature_row, status_siaga):
    """Diagnosis penyebab banjir berdasarkan data sensor."""
    if status_siaga == "SIAGA 3":
        return "Kondisi aman, pemantauan rutin."

    causes = []

    # Hujan lokal berdasarkan akumulasi
    if float(feature_row.get("Rain_30min", 0)) >= 10:
        causes.append("Hujan lokal intensitas tinggi (30 menit terakhir)")
    if float(feature_row.get("Rain_1h", 0)) >= 20:
        causes.append("Hujan lokal lebat (1 jam terakhir)")
    if float(feature_row.get("Rain_3h", 0)) >= 30:
        causes.append("Akumulasi hujan tinggi (3 jam terakhir)")
    if float(feature_row.get("Rain_6h", 0)) >= 50:
        causes.append("Akumulasi hujan sangat tinggi (6 jam terakhir)")

    # Banjir kiriman dari hulu:
    # air naik cepat (distance turun banyak) TANPA hujan lokal signifikan
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

    # Tekanan udara rendah → cuaca buruk
    if float(feature_row.get("SeaLevelPressure_hPa", 1013)) <= 1005:
        causes.append("Tekanan udara rendah, indikasi cuaca buruk")

    # Konfirmasi fisik
    if float(feature_row.get("RiverWaterLevel_m", 10)) <= THRESHOLD_SIAGA_1_M:
        causes.append("Air sudah mencapai permukaan jalan, banjir terkonfirmasi")

    if not causes:
        causes.append("Banjir terdeteksi, penyebab dominan belum teridentifikasi")

    return " | ".join(causes)

def convert_sensor_data_for_prediction(raw_data):
    """
    Konversi paket sensor ke format input model.

    Catatan satuan:
      - raw_data['jarak_air'] di sini sudah dalam SENTIMETER
        (sudah dikonversi mm -> cm di merge_with_last_data()).
      - Dibagi CM_TO_M_DIVISOR (=100) untuk dapat METER, yang dipakai
        sebagai input fitur model (RiverWaterLevel_m).
    """
    jarak_air_cm = raw_data.get("jarak_air", 0)
    if jarak_air_cm is None:
        jarak_air_cm = 0
    distance_m = float(jarak_air_cm) / CM_TO_M_DIVISOR

    return {
        "timestamp":            datetime.datetime.now(),
        "Temperature_C":        float(raw_data.get("suhu", 0) or 0),
        "Humidity_percent":     float(raw_data.get("kelembapan", 0) or 0),
        "SeaLevelPressure_hPa": float(raw_data.get("tekanan", 1013) or 1013),
        "Precipitation_mm":     float(raw_data.get("rain_rate", 0) or 0),
        "RiverWaterLevel_m":    float(distance_m)
    }

def build_features_for_prediction(current_data):
    """Bangun fitur untuk ML berdasarkan history."""
    history.append(current_data)
    df_hist = pd.DataFrame(list(history))

    current_distance = float(current_data["RiverWaterLevel_m"])
    current_precipitation = float(current_data["Precipitation_mm"])

    # Akumulasi hujan; kalau history kurang, estimasi linear
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
    """Prediksi banjir via RF (kalau ada) atau rule-based fallback."""
    if not model_loaded or rf is None:
        # Fallback rule-based pakai threshold SIAGA fisik
        jarak = float(feature_row.get("RiverWaterLevel_m", 10))
        if jarak <= THRESHOLD_SIAGA_1_M:
            return 0.95, 0.95, 1
        elif jarak <= THRESHOLD_SIAGA_2_M:
            return 0.7, 0.7, 1
        else:
            return 0.1, 0.1, 0

    try:
        X = pd.DataFrame([feature_row])
        X_model = X[features]
        rf_prob = float(rf.predict_proba(X_model)[:, 1][0])
        final_prob = float(rf_prob)
        pred_alert = int(final_prob >= threshold)
        return rf_prob, final_prob, pred_alert
    except Exception as e:
        print(f"⚠️ Prediction error: {e}")
        return 0.0, 0.0, 0

def save_prediction_log(result):
    """Append hasil prediksi ke CSV."""
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

# ----------------------------------------------------------------
# AUTO CREATE TABLES
# ----------------------------------------------------------------
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
    rssi INTEGER
)
""")
conn.commit()

cur.execute("""
CREATE TABLE IF NOT EXISTS flood_prediction (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    distance_to_water_m REAL,
    water_height_m REAL,
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

# Schema safety net: amankan kolom water_height_m kalau tabel sudah ada
try:
    cur.execute("ALTER TABLE flood_prediction ADD COLUMN IF NOT EXISTS water_height_m REAL;")
    conn.commit()
except Exception:
    conn.rollback()

cur.execute("""
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    rssi INTEGER,
    noise_level VARCHAR(20),
    cpu_percent REAL,
    memory_percent REAL,
    memory_used_mb REAL,
    memory_total_mb REAL,
    disk_percent REAL,
    disk_used_gb REAL,
    disk_total_gb REAL,
    load_avg_1min REAL,
    load_avg_5min REAL,
    load_avg_15min REAL,
    temperature_celsius REAL
)
""")
conn.commit()
print("🛢 Tables Ready (sensor_log, flood_prediction, system_metrics)")

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

# # ===============================================================
# # TAMBAHAN PENDUKUNG QOS REAL-TIME (TIDAK MERUSAK KODE ASLI)
# # ===============================================================
# QOS_JSON_LOG_PATH = "qos_log.json"

# qos_state = {
#     "total_packet_expected": 0,
#     "total_packet_received": 0,
#     "last_sequence_number": None,
#     "initial_sequence_number": None,
#     "last_packet_timestamp": None,
#     "last_delay_ms": 0,
#     "jitter_accumulator": 0.0,
#     "history_delay": []
# }

# def noise_label(v):
#     if v <= -115: return "Bersih"
#     elif v <= -105: return "Normal"
#     elif v <= -95: return "Sedikit Noise"
#     else: return "Bising"

# ===============================================================
# CONFIG / STATE
# ===============================================================
FREQ = 915.0
TOTAL_PACKET = 0
LAST_WAIT_PRINT = 0
CSV_EXPORT_INTERVAL = 60
LAST_CSV_EXPORT = 0
SYSTEM_METRICS_INTERVAL = 30  # Kirim metrics ke Postgres tiap 30 detik
LAST_SYSTEM_METRICS = 0

LAST_COMPLETE_DATA = {}
LAST_PREDICTION_RESULT = None

# ===============================================================
# INIT LORA
# ===============================================================
# LoRa settings: pakai yg lebih robust (tx_power=15, coding_rate=6)
# untuk jangkauan lebih jauh / lebih tahan noise, walau throughput turun.
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.D4)
reset = digitalio.DigitalInOut(board.D25)
rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, FREQ)
rfm9x.tx_power = 15
rfm9x.signal_bandwidth = 125000
rfm9x.coding_rate = 6
rfm9x.spreading_factor = 10
rfm9x.enable_crc = True
rfm9x.sync_word = 0x12
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
    """
    Gabungkan paket sensor terbaru dengan cache paket terakhir.
    Field 'd' (jarak air) dikonversi mm -> cm di sini.
    Setelah fungsi ini, 'd' di LAST_COMPLETE_DATA satuannya CM.
    """
    global LAST_COMPLETE_DATA
    important_keys = ['t', 'h', 'p', 'd']
    is_complete = any(k in data for k in important_keys)

    if is_complete:
        LAST_COMPLETE_DATA.update(data)
        if 'd' in LAST_COMPLETE_DATA:
            LAST_COMPLETE_DATA['d'] = round(float(LAST_COMPLETE_DATA['d']) / 10, 1)
        return LAST_COMPLETE_DATA.copy()
    else:
        merged = LAST_COMPLETE_DATA.copy()
        merged.update(data)
        return merged

# ===============================================================
# UPDATE FIREBASE
# ===============================================================
def update_firebase_with_prediction(sensor_data, prediction_result, rssi, system_metrics):
    """Push ke Firebase: data sensor + prediksi + system metrics."""
    try:
        current_time = datetime.datetime.now()
        timestamp_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

        sensor_data       = convert_numpy_types(sensor_data)
        prediction_result = convert_numpy_types(prediction_result or {})
        system_metrics    = convert_numpy_types(system_metrics)

        payload = {
            "timestamp":   timestamp_str,
            "suhu":        float(sensor_data.get('t', 0) or 0),
            "kelembapan":  float(sensor_data.get('h', 0) or 0),
            "tekanan":     float(sensor_data.get('p', 0) or 0),
            "jarak_air":   float(sensor_data.get('d', 0) or 0),       # CM, raw distance
            "flow":        float(sensor_data.get('f', 0) or 0),
            "rain_total":  float(sensor_data.get('rt', 0) or 0),
            "rain_rate":   float(sensor_data.get('rr', 0) or 0),
            "float_level": float(sensor_data.get('lv', 0) or 0),
            "alert":       str(sensor_data.get('al', 'NORMAL')),
            "seq":         int(sensor_data.get('sq', 0) or 0),
            "rssi":        int(rssi),
            "status":      "Monitoring",

            # ---- DATA PREDIKSI & UI ----
            "prediction_status":   str(prediction_result.get("status", "SIAGA 3")),
            "is_flooded":          bool(prediction_result.get("is_flooded", False)),
            "probability":         round(float(prediction_result.get("final_prob", 0)) * 100, 2),

            # Khusus tampilan dashboard (M, dari dasar sungai)
            "water_height_m":      float(prediction_result.get("water_height_m", 0)),

            # Raw distance dari sensor (M, untuk log/audit ML)
            "distance_to_water_m": float(prediction_result.get("distance_to_water_m", 0)),

            "affected_area_ha":    float(prediction_result.get("affected_area_ha", 0)),
            "affected_kk":         int(prediction_result.get("affected_kk", 0)),
            "total_budget_idr":    int(prediction_result.get("total_budget_idr", 0)),
            "diagnosis":           str(prediction_result.get("diagnosis", "")),

            # ---- SYSTEM METRICS (untuk dashboard kesehatan device) ----
            "cpu_percent":         system_metrics.get("cpu_percent", 0),
            "memory_percent":      system_metrics.get("memory_percent", 0),
            "memory_used_mb":      system_metrics.get("memory_used_mb", 0),
            "memory_total_mb":     system_metrics.get("memory_total_mb", 0),
            "disk_percent":        system_metrics.get("disk_percent", 0),
            "disk_used_gb":        system_metrics.get("disk_used_gb", 0),
            "disk_total_gb":       system_metrics.get("disk_total_gb", 0),
            "load_avg_1min":       system_metrics.get("load_avg_1min", 0),
            "load_avg_5min":       system_metrics.get("load_avg_5min", 0),
            "load_avg_15min":      system_metrics.get("load_avg_15min", 0),
            "temperature_celsius": system_metrics.get("temperature_celsius")
        }

        # Latest snapshot (overwrite tiap paket)
        db.child("node1").child("latest").child(UID).set(payload, token)
        # History (push-append)
        db.child("node1").child("history").child(UID).push(payload, token)
        # Node monitoring kesehatan device terpisah
        db.child("system_monitoring").child(UID).set({
            "timestamp": timestamp_str,
            **system_metrics,
            "rssi": int(rssi),
            "noise_status": noise_label(rssi)
        }, token)

        print("☁️ Firebase Updated (sensor + prediction + system metrics)")

    except Exception as e:
        print(f"❌ Firebase Update Error: {e}")

def save_system_metrics_to_db(rssi, system_metrics):
    """Simpan system metrics ke tabel system_metrics."""
    try:
        cur.execute("""
        INSERT INTO system_metrics (
            timestamp, rssi, noise_level, cpu_percent, memory_percent,
            memory_used_mb, memory_total_mb, disk_percent, disk_used_gb,
            disk_total_gb, load_avg_1min, load_avg_5min, load_avg_15min,
            temperature_celsius
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            datetime.datetime.now(),
            int(rssi),
            noise_label(rssi),
            system_metrics.get("cpu_percent"),
            system_metrics.get("memory_percent"),
            system_metrics.get("memory_used_mb"),
            system_metrics.get("memory_total_mb"),
            system_metrics.get("disk_percent"),
            system_metrics.get("disk_used_gb"),
            system_metrics.get("disk_total_gb"),
            system_metrics.get("load_avg_1min"),
            system_metrics.get("load_avg_5min"),
            system_metrics.get("load_avg_15min"),
            system_metrics.get("temperature_celsius")
        ))
        conn.commit()
        print("🛢 System metrics saved to PostgreSQL")
    except Exception as e:
        print(f"❌ DB Save Metrics Error: {e}")
        conn.rollback()

# ===============================================================
# PROSES PREDIKSI
# ===============================================================
def process_prediction(sensor_dict, rssi):
    """Jalankan prediksi berdasarkan paket sensor terbaru."""
    global last_prediction_time, history

    current_time = datetime.datetime.now()

    # Throttle: maks 1 prediksi per SENSOR_INTERVAL_SECONDS
    if last_prediction_time is not None:
        time_diff = (current_time - last_prediction_time).total_seconds()
        if time_diff < SENSOR_INTERVAL_SECONDS:
            return None

    converted = convert_sensor_data_for_prediction(sensor_dict)
    feature_row = build_features_for_prediction(converted)

    if len(history) < MIN_HISTORY_FOR_PREDICTION:
        print(f"📊 Collecting history for prediction... {len(history)}/{MIN_HISTORY_FOR_PREDICTION}")
        return None

    rf_prob, final_prob, pred_alert = predict_flood(feature_row)
    distance_to_water_m = float(converted["RiverWaterLevel_m"])
    status_siaga = get_siaga_status(pred_alert, distance_to_water_m)
    is_flooded = status_siaga in ("SIAGA 1", "SIAGA 2")

    # ---- KONVERSI UI: distance-to-water -> water_height ----
    # Tinggi air = (jarak sensor ke dasar) - (jarak sensor ke permukaan air)
    tinggi_air_m = JARAK_DASAR_SUNGAI_M - distance_to_water_m
    tinggi_air_m = max(0.0, float(tinggi_air_m))

    # Estimasi dampak
    affected_area_ha = estimate_affected_area_ha(status_siaga)
    affected_area_m2 = ha_to_m2(affected_area_ha)
    affected_kk = estimate_affected_kk(affected_area_ha)
    total_budget, bantuan_per_kk = estimate_budget(affected_kk, status_siaga)

    diagnosis = diagnose_flood_cause(feature_row, status_siaga)

    prediction_result = {
        "timestamp":               converted["timestamp"],
        "distance_to_water_m":     float(distance_to_water_m),
        "water_height_m":          float(tinggi_air_m),
        "rf_prob":                 float(rf_prob),
        "final_prob":              float(final_prob),
        "threshold":               float(threshold),
        "pred_alert":              int(pred_alert),
        "status":                  str(status_siaga),
        "is_flooded":              bool(is_flooded),
        "affected_area_ha":        float(affected_area_ha),
        "affected_area_m2":        int(affected_area_m2),
        "affected_kk":             int(affected_kk),
        "bantuan_per_kk_idr":      int(bantuan_per_kk),
        "total_budget_idr":        int(total_budget),
        "diagnosis":               str(diagnosis),
        "suhu":                    float(feature_row["Temperature_C"]),
        "kelembapan":              float(feature_row["Humidity_percent"]),
        "tekanan":                 float(feature_row["SeaLevelPressure_hPa"]),
        "rain_rate":               float(feature_row["Precipitation_mm"]),
        "rain_30min":              float(feature_row["Rain_30min"]),
        "rain_1h":                 float(feature_row["Rain_1h"]),
        "rain_3h":                 float(feature_row["Rain_3h"]),
        "rain_6h":                 float(feature_row["Rain_6h"]),
        "water_level_change_30min": float(feature_row["WaterLevel_Change_30min"]),
        "water_level_change_1h":    float(feature_row["WaterLevel_Change_1h"]),
        "water_level_change_3h":    float(feature_row["WaterLevel_Change_3h"])
    }

    # Print hasil
    print("\n" + "=" * 50)
    print("🔮 FLOOD PREDICTION RESULT")
    print("=" * 50)
    print(f"📊 Status Siaga    : {status_siaga}")
    print(f"🌊 Tinggi Air      : {round(tinggi_air_m, 2)} m")
    print(f"📏 Jarak ke Air    : {round(distance_to_water_m, 3)} m (raw)")
    print(f"📈 Probabilitas    : {round(final_prob * 100, 2)}%")
    print(f"🏠 Luas Terdampak  : {affected_area_ha} Ha ({affected_area_m2} m²)")
    print(f"👨‍👩‍👧‍👦 KK Terdampak    : {affected_kk} KK")
    print(f"💰 Total Bantuan   : {format_rupiah(total_budget)}")
    print(f"📋 Diagnosis       : {diagnosis}")
    print("=" * 50)

    # Simpan ke Postgres
    try:
        cur.execute("""
        INSERT INTO flood_prediction (
            timestamp, distance_to_water_m, water_height_m, rf_prob, final_prob, threshold,
            pred_alert, status, is_flooded, affected_area_ha, affected_area_m2,
            affected_kk, bantuan_per_kk_idr, total_budget_idr, diagnosis,
            suhu, kelembapan, tekanan, rain_rate, rain_30min, rain_1h,
            rain_3h, rain_6h, water_level_change_30min, water_level_change_1h,
            water_level_change_3h
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            prediction_result["timestamp"],
            prediction_result["distance_to_water_m"],
            prediction_result["water_height_m"],
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

    save_prediction_log(prediction_result)

    # Alert console
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
def tampilkan_data(data, rssi, system_metrics):
    global TOTAL_PACKET
    TOTAL_PACKET += 1
    print("\n" + "═" * 70)
    print(f"📩 DATA #{TOTAL_PACKET}")
    print(f"🕒 Waktu : {datetime.datetime.now().strftime('%H:%M:%S')}")
    print(f"📶 RSSI  : {rssi} dBm ({noise_label(rssi)})")
    print(f"🌡️ Suhu  : {data.get('t', 'N/A')}")
    print(f"💧 Hum   : {data.get('h', 'N/A')}")
    print(f"🎯 Tekanan: {data.get('p', 'N/A')}")
    print(f"🌊 Jarak : {data.get('d', 'N/A')} cm (raw, sensor -> air)")
    print(f"💧 Float : {data.get('lv', 'N/A')}")
    print(f"⚠️ Alert : {data.get('al', 'NORMAL')}")
    print(f"🔢 Seq   : {data.get('sq', 'N/A')}")
    print("-" * 35)
    print("📊 SYSTEM METRICS:")
    print(f"💻 CPU    : {system_metrics.get('cpu_percent', 0)}%")
    print(f"🧠 Memory : {system_metrics.get('memory_percent', 0)}% "
          f"({system_metrics.get('memory_used_mb', 0):.0f}/{system_metrics.get('memory_total_mb', 0):.0f} MB)")
    print(f"💾 Disk   : {system_metrics.get('disk_percent', 0)}% "
          f"({system_metrics.get('disk_used_gb', 0):.1f}/{system_metrics.get('disk_total_gb', 0):.1f} GB)")
    if system_metrics.get('temperature_celsius'):
        print(f"🌡️ Pi Temp: {system_metrics.get('temperature_celsius', 0):.1f}°C")
    print("═" * 70)

# ===============================================================
# SAVE POSTGRESQL (sensor_log)
# ===============================================================
def simpan_postgresql(data, rssi):
    try:
        cur.execute("""
        INSERT INTO sensor_log (
            waktu, suhu, kelembapan, tekanan, jarak_air,
            flow, rain_total, rain_rate, float_level, alert, seq, rssi
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            int(rssi)
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
# MAIN LOOP
# ===============================================================
print("📡 Receiver Ready with Flood Prediction & System Monitoring")
print(f"   JARAK_DASAR_SUNGAI_M = {JARAK_DASAR_SUNGAI_M} m "
      f"⚠️ pastikan ini sesuai instalasi lapangan")
print("-" * 70)

# # QOS
# def calculate_realtime_qos(current_sq, packet_size_bytes, current_rssi, current_snr):
#     now = datetime.datetime.now()
#     current_timestamp = time.time()
    
#     if qos_state["initial_sequence_number"] is None:
#         qos_state["initial_sequence_number"] = current_sq
#         qos_state["total_packet_expected"] = 1
#     else:
#         qos_state["total_packet_expected"] = (current_sq - qos_state["initial_sequence_number"]) + 1

# # packet loss: hitung berdasarkan selisih sequence number (anggap urut, tanpa duplikat) 
#     qos_state["total_packet_received"] += 1
#     lost_packets = qos_state["total_packet_expected"] - qos_state["total_packet_received"]
#     packet_loss_percent = (max(0, lost_packets) / qos_state["total_packet_expected"]) * 100.0
# # delay: estimasi waktu on-air + faktor gangguan sinyal (berdasarkan RSSI)
#     base_time_on_air_ms = 328.0  # Karakteristik SF10
#     signal_interference_factor = abs(current_rssi + 100) * 0.5
#     current_delay_ms = base_time_on_air_ms + signal_interference_factor
#     qos_state["history_delay"].append(current_delay_ms)
# # jitter: variasi delay antar paket, dihitung sebagai rata-rata bergerak dari selisih delay
#     jitter_ms = 0.0
#     if qos_state["last_packet_timestamp"] is not None:
#         delay_difference = abs(current_delay_ms - qos_state["last_delay_ms"])
#         qos_state["jitter_accumulator"] += (delay_difference - qos_state["jitter_accumulator"]) / 16.0
#         jitter_ms = qos_state["jitter_accumulator"]
# # throughput: hitung berdasarkan ukuran paket dan durasi antar paket, tapi gunakan interval minimal untuk menghindari spike saat paket datang berdekatan
#     if qos_state["last_packet_timestamp"] is not None:
#         duration_seconds = current_timestamp - qos_state["last_packet_timestamp"]
#         # Jika jeda terlalu rapat, gunakan interval pengiriman sensor (30 detik)
#         throughput_bps = (packet_size_bytes * 8) / duration_seconds if duration_seconds > 0 else (packet_size_bytes * 8) / 30
#     else:
#         throughput_bps = (packet_size_bytes * 8) / 30

#     qos_state["last_sequence_number"] = current_sq
#     qos_state["last_packet_timestamp"] = current_timestamp
#     qos_state["last_delay_ms"] = current_delay_ms

#     return {
#         "waktu": now.strftime("%Y-%m-%d %H:%M:%S"), 
#         "seq_number": int(current_sq), 
#         "packet_size_bytes": int(packet_size_bytes),
#         "delay_ms": round(float(current_delay_ms), 2), 
#         "throughput_bps": round(float(throughput_bps), 2),
#         "packet_loss_percent": round(float(packet_loss_percent), 2), 
#         "jitter_ms": round(float(jitter_ms), 2),
#         "rssi": int(current_rssi), 
#         "snr": round(float(current_snr), 1),
#         "noise_status": noise_label(current_rssi)
#     }

# def write_qos_to_json(qos_metrics):
#     try:
#         log_data = []
#         if os.path.exists(QOS_JSON_LOG_PATH):
#             with open(QOS_JSON_LOG_PATH, 'r') as file:
#                 try:
#                     log_data = json.load(file)
#                     if not isinstance(log_data, list): log_data = []
#                 except json.JSONDecodeError: log_data = []
        
#         log_data.append(qos_metrics)
#         with open(QOS_JSON_LOG_PATH, 'w') as file:
#             json.dump(log_data, file, indent=4)
#     except Exception as e:
#         print(f" ❌ Gagal menulis berkas log JSON: {e}")
# # QOS: hitung packet loss, delay, jitter berdasarkan sequence number dan timestamp

while True:
    try:
        packet = rfm9x.receive(timeout=1.0)
        if packet is not None:
            packet_size = len(packet)
            try:
                raw_packet_string = str(packet, 'utf-8')
                data = parse_packet(raw_packet_string)
            except Exception as parse_err:
                continue
            
            if data and 'sq' in data:
                current_sq = int(data.get('sq'))
                current_rssi = int(rfm9x.last_rssi)
                current_snr = float(rfm9x.last_snr)

                qos_metrics = calculate_realtime_qos(current_sq, packet_size, current_rssi, current_snr)
                write_qos_to_json(qos_metrics)
                print(f"\n[QoS LIVE LOG - SQ: {current_sq}] Delay: {qos_metrics['delay_ms']}ms | Loss: {qos_metrics['packet_loss_percent']}% | RSSI: {current_rssi} dBm | SNR: {current_snr} dB")
        current_time = time.time()

        # Selalu refresh system metrics (dipakai di display + Firebase + waiting print)
        system_metrics = get_system_metrics()
        rssi_current   = get_live_rssi()

        # Simpan metrics ke Postgres secara periodik (independen dari kedatangan paket)
        if current_time - LAST_SYSTEM_METRICS >= SYSTEM_METRICS_INTERVAL:
            save_system_metrics_to_db(rssi_current, system_metrics)
            LAST_SYSTEM_METRICS = current_time

        if packet is not None:
            raw_str = packet.decode("utf-8", errors="ignore")
            data = parse_packet(raw_str)

            if data and len(data) > 0:
                rssi = rfm9x.last_rssi

                # Merge partial -> full data (sekaligus konversi mm -> cm)
                final_data = merge_with_last_data(data)

                # Simpan ke sensor_log
                simpan_postgresql(final_data, rssi)

                # Prediksi
                prediction_result = process_prediction(final_data, rssi)

                # Push ke Firebase: sensor + prediksi + system metrics
                update_firebase_with_prediction(
                    final_data, prediction_result or {}, rssi, system_metrics
                )

                # Display
                tampilkan_data(final_data, rssi, system_metrics)

            else:
                print("❌ Gagal parse packet")
        else:
            now = time.time()
            if now - LAST_WAIT_PRINT >= 2:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                      f"⌛ Waiting... | RSSI: {rssi_current} dBm | {noise_label(rssi_current)} | "
                      f"CPU: {system_metrics.get('cpu_percent', 0)}% | "
                      f"Mem: {system_metrics.get('memory_percent', 0)}%")
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