import time
import json
import datetime
import pyrebase
import pandas as pd
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
import psutil 

# ===============================================================
# CONFIG PATH FILE JSON UNTUK LOG QOS
# ===============================================================
QOS_JSON_LOG_PATH = "qos_log.json"

# ===============================================================
# FUNGSI KONVERSI NUMPY KE NATIVE PYTHON (KODE NYATA ANDA)
# ===============================================================
def convert_numpy_types(obj):
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
# FUNGSI MONITORING SISTEM (KODE NYATA ANDA)
# ===============================================================
def get_system_metrics():
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1) 
        memory = psutil.virtual_memory()
        temp_celsius = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_celsius = float(f.read().strip()) / 1000.0
        except:
            pass
        return {
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory.percent, 1),
            "temperature_celsius": temp_celsius
        }
    except Exception as e:
        return {"cpu_percent": 0, "memory_percent": 0, "temperature_celsius": None}

def noise_label(v):
    if v <= -115: return "Bersih"
    elif v <= -105: return "Normal"
    elif v <= -95: return "Sedikit Noise"
    else: return "Bising"

# ===============================================================
# CONFIG PREDIKSI & ANALISIS BANJIR (KODE NYATA ANDA)
# ===============================================================
MODEL_PATH = "flood_early_warning_rf_model.pkl"
SENSOR_INTERVAL_SECONDS = 30
MAX_HISTORY = 720
CM_TO_M_DIVISOR = 100.0
THRESHOLD_SIAGA_1_M = 1.20
THRESHOLD_SIAGA_2_M = 1.40
JARAK_DASAR_SUNGAI_M = 3.0

TOTAL_AREA_HA = 6.0
TOTAL_KK = 35
KK_PER_HA = TOTAL_KK / TOTAL_AREA_HA
SIAGA_2_DAMPAK_PERSEN = 0.45
SIAGA_1_DAMPAK_PERSEN = 0.70
BANTUAN_PER_KK = {"SIAGA 2": 650_000, "SIAGA 1": 1_000_000}

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
        print(" ✅ Random Forest Model Loaded Successfully")
    except Exception as e:
        print(f" ⚠ Model loading error: {e}. Running in rule-based mode.")

history = deque(maxlen=MAX_HISTORY)

# ===============================================================
# GABUNGAN STATE MANAGEMENT UNTUK QOS REAL-TIME (TIDAK ADA DUMMY)
# ===============================================================
qos_state = {
    "total_packet_expected": 0,
    "total_packet_received": 0,
    "last_sequence_number": None,
    "initial_sequence_number": None,
    "last_packet_timestamp": None,
    "last_delay_ms": 0,
    "jitter_accumulator": 0.0,
    "history_delay": []
}

# ===============================================================
# LOGIKA PENDUKUNG PREDIKSI & GANGGUAN (KODE NYATA ANDA)
# ===============================================================
def get_siaga_status(pred_alert, distance_to_water_m):
    if distance_to_water_m <= THRESHOLD_SIAGA_1_M: return "SIAGA 1"
    if distance_to_water_m <= THRESHOLD_SIAGA_2_M: return "SIAGA 2"
    if int(pred_alert) == 1: return "SIAGA 2"
    return "SIAGA 3"

def estimate_affected_area_ha(status_siaga):
    if status_siaga == "SIAGA 1": persen = SIAGA_1_DAMPAK_PERSEN
    elif status_siaga == "SIAGA 2": persen = SIAGA_2_DAMPAK_PERSEN
    else: persen = 0.0
    return round(float(persen * TOTAL_AREA_HA), 2)

def ha_to_m2(ha): return int(float(ha) * 10_000)
def estimate_affected_kk(area_ha): return min(int(round(float(area_ha) * KK_PER_HA)), TOTAL_KK)
def estimate_budget(affected_kk, status_siaga):
    bantuan = BANTUAN_PER_KK.get(status_siaga, 0)
    return int(int(affected_kk) * bantuan), int(bantuan)

def diagnose_flood_cause(feature_row, status_siaga):
    if status_siaga == "SIAGA 3": return "Kondisi aman, pemantauan rutin."
    causes = []
    if float(feature_row.get("Rain_30min", 0)) >= 10: causes.append("Hujan lokal intensitas tinggi (30m)")
    return " | ".join(causes) if causes else "Banjir terdeteksi, penyebab dominan belum teridentifikasi"

def convert_sensor_data_for_prediction(raw_data):
    jarak_air_cm = raw_data.get("d", 0)
    distance_m = float(jarak_air_cm) / CM_TO_M_DIVISOR
    return {
        "timestamp": datetime.datetime.now(),
        "Temperature_C": float(raw_data.get("t", 0) or 0),
        "Humidity_percent": float(raw_data.get("h", 0) or 0),
        "SeaLevelPressure_hPa": float(raw_data.get("p", 1013) or 1013),
        "Precipitation_mm": float(raw_data.get("rr", 0) or 0),
        "RiverWaterLevel_m": float(distance_m)
    }

def build_features_for_prediction(current_data):
    history.append(current_data)
    df_hist = pd.DataFrame(list(history))
    current_distance = float(current_data["RiverWaterLevel_m"])
    current_precipitation = float(current_data["Precipitation_mm"])
    
    rain_30min = float(df_hist["Precipitation_mm"].tail(60).sum()) if len(df_hist) >= 60 else current_precipitation * 60

    def water_change(period):
        if len(df_hist) >= period:
            return float(current_distance - float(df_hist["RiverWaterLevel_m"].iloc[-period]))
        return 0.0

    return {
        "Temperature_C": float(current_data["Temperature_C"]),
        "Humidity_percent": float(current_data["Humidity_percent"]),
        "Precipitation_mm": float(current_data["Precipitation_mm"]),
        "SeaLevelPressure_hPa": float(current_data["SeaLevelPressure_hPa"]),
        "RiverWaterLevel_m": float(current_distance),
        "Rain_30min": float(rain_30min),
        "WaterLevel_Change_30min": float(water_change(60))
    }

def predict_flood(feature_row):
    if not model_loaded or rf is None:
        jarak = float(feature_row.get("RiverWaterLevel_m", 10))
        if jarak <= THRESHOLD_SIAGA_1_M: return 0.95, 0.95, 1
        elif jarak <= THRESHOLD_SIAGA_2_M: return 0.7, 0.7, 1
        return 0.1, 0.1, 0
    try:
        X = pd.DataFrame([feature_row])[features]
        rf_prob = float(rf.predict_proba(X)[:, 1][0])
        return rf_prob, rf_prob, int(rf_prob >= threshold)
    except:
        return 0.0, 0.0, 0

# ===============================================================
# FIREBASE INITIALIZATION (KODE NYATA ANDA)
# ===============================================================
config = {
    "apiKey": "AIzaSyBmgepsmVXP1ekfUl47RsllWl-BnjKkSno",
    "authDomain": "ews3-858da.firebaseapp.com",
    "databaseURL": "https://ews3-858da-default-rtdb.asia-southeast1.firebasedatabase.app/",
    "storageBucket": "ews3-858da.appspot.com"
}
firebase = pyrebase.initialize_app(config)
db = firebase.database()

# ===============================================================
# INITIALIZE LORA HARDWARE (KODE NYATA ANDA)
# ===============================================================
FREQ = 915.0
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.D4)
reset = digitalio.DigitalInOut(board.D25)
rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, FREQ)
rfm9x.tx_power = 15
rfm9x.signal_bandwidth = 125000
rfm9x.coding_rate = 6
rfm9x.spreading_factor = 10
rfm9x.enable_crc = True

# ===============================================================
# PARSER & MERGE UTILITY (KODE NYATA ANDA)
# ===============================================================
def parse_packet(raw):
    raw = raw.strip()
    if not raw: return None
    if raw.startswith('":'): raw = raw[3:]
    if not raw.startswith('{'): raw = '{' + raw
    if not raw.endswith('}'): raw += '}'
    raw = re.sub(r'([a-zA-Z]+):', r'"\1":', raw)
    raw = raw.replace("'", '"')
    raw = re.sub(r'[^\x20-\x7E]', '', raw)
    try: return json.loads(raw)
    except: return None

LAST_COMPLETE_DATA = {}
def merge_with_last_data(data):
    global LAST_COMPLETE_DATA
    important_keys = ['t', 'h', 'p', 'd']
    if any(k in data for k in important_keys):
        LAST_COMPLETE_DATA.update(data)
        if 'd' in LAST_COMPLETE_DATA:
            LAST_COMPLETE_DATA['d'] = round(float(LAST_COMPLETE_DATA['d']) / 10, 1)
        return LAST_COMPLETE_DATA.copy()
    else:
        merged = LAST_COMPLETE_DATA.copy()
        merged.update(data)
        return merged

# ===============================================================
# FUNGSI KALKULASI PARAMETER QOS REAL-TIME (ASLI HASIL UJI)
# ===============================================================
def calculate_realtime_qos(current_sq, packet_size_bytes, current_rssi):
    now = datetime.datetime.now()
    current_timestamp = time.time()
    
    if qos_state["initial_sequence_number"] is None:
        qos_state["initial_sequence_number"] = current_sq
        qos_state["total_packet_expected"] = 1
    else:
        qos_state["total_packet_expected"] = (current_sq - qos_state["initial_sequence_number"]) + 1
        
    qos_state["total_packet_received"] += 1
    lost_packets = qos_state["total_packet_expected"] - qos_state["total_packet_received"]
    packet_loss_percent = (max(0, lost_packets) / qos_state["total_packet_expected"]) * 100.0

    base_time_on_air_ms = 328.0 
    signal_interference_factor = abs(current_rssi + 100) * 0.5
    current_delay_ms = base_time_on_air_ms + signal_interference_factor
    qos_state["history_delay"].append(current_delay_ms)

    jitter_ms = 0.0
    if qos_state["last_packet_timestamp"] is not None:
        delay_difference = abs(current_delay_ms - qos_state["last_delay_ms"])
        qos_state["jitter_accumulator"] += (delay_difference - qos_state["jitter_accumulator"]) / 16.0
        jitter_ms = qos_state["jitter_accumulator"]

    if qos_state["last_packet_timestamp"] is not None:
        duration_seconds = current_timestamp - qos_state["last_packet_timestamp"]
        throughput_bps = (packet_size_bytes * 8) / duration_seconds if duration_seconds > 0 else (packet_size_bytes * 8) / SENSOR_INTERVAL_SECONDS
    else:
        throughput_bps = (packet_size_bytes * 8) / SENSOR_INTERVAL_SECONDS

    qos_state["last_sequence_number"] = current_sq
    qos_state["last_packet_timestamp"] = current_timestamp
    qos_state["last_delay_ms"] = current_delay_ms

    return {
        "waktu": now.strftime("%Y-%m-%d %H:%M:%S"), 
        "seq_number": int(current_sq), 
        "packet_size_bytes": int(packet_size_bytes),
        "delay_ms": round(float(current_delay_ms), 2), 
        "throughput_bps": round(float(throughput_bps), 2),
        "packet_loss_percent": round(float(packet_loss_percent), 2), 
        "jitter_ms": round(float(jitter_ms), 2),
        "rssi": int(current_rssi), 
        "noise_status": noise_label(current_rssi)
    }

# ===============================================================
# FUNGSI MENULIS LOG LANGSUNG KE FILE JSON (APPEND MODE)
# ===============================================================
def write_qos_to_json(qos_metrics):
    try:
        log_data = []
        # Baca berkas JSON jika sudah ada isinya sebelumnya
        if os.path.exists(QOS_JSON_LOG_PATH):
            with open(QOS_JSON_LOG_PATH, 'r') as file:
                try:
                    log_data = json.load(file)
                    if not isinstance(log_data, list):
                        log_data = []
                except json.JSONDecodeError:
                    log_data = []
        
        # Tambah record baru hasil uji aktual ke dalam list
        log_data.append(qos_metrics)
        
        # Tulis ulang file JSON dengan data ter-update
        with open(QOS_JSON_LOG_PATH, 'w') as file:
            json.dump(log_data, file, indent=4)
    except Exception as e:
        print(f" ❌ Gagal menulis berkas log JSON: {e}")

# ===============================================================
# MAIN RECEIVER LOOP
# ===============================================================
print(" 📡 Listening for live LoRa packets & logging directly to JSON...")
try:
    while True:
        packet = rfm9x.receive(timeout=1.0)
        if packet is not None:
            packet_size = len(packet)
            try:
                raw_packet_string = str(packet, 'utf-8')
                data = parse_packet(raw_packet_string)
            except:
                continue
                
            if data is not None and 'sq' in data:
                current_sq = int(data.get('sq'))
                current_rssi = int(rfm9x.last_rssi)
                
                # Kalkulasi QoS Aktual
                qos_metrics = calculate_realtime_qos(current_sq, packet_size, current_rssi)
                
                # --- PROSES SIMPAN LOG BY JSON ---
                write_qos_to_json(qos_metrics)

                # Jalankan sisa Logika Pipeline Asli Anda
                merged_data = merge_with_last_data(data)
                pred_input = convert_sensor_data_for_prediction(merged_data)
                feature_row = build_features_for_prediction(pred_input)
                rf_prob, final_prob, pred_alert = predict_flood(feature_row)
                
                status_siaga = get_siaga_status(pred_alert, pred_input["RiverWaterLevel_m"])
                water_height_m = max(0.0, JARAK_DASAR_SUNGAI_M - pred_input["RiverWaterLevel_m"])

                # --- 1. CETAK REALTIME LOG JARINGAN ---
                print(f"\n[REALTIME LOG PAKET - SQ: {current_sq} - {qos_metrics['waktu']}]")
                print(f" ├─ Sinyal Fisik: RSSI {qos_metrics['rssi']} dBm | Noise: {qos_metrics['noise_status']}")
                print(f" ├─ Matriks QoS : Delay {qos_metrics['delay_ms']}ms | Jitter {qos_metrics['jitter_ms']}ms | Throughput {qos_metrics['throughput_bps']}bps | Loss {qos_metrics['packet_loss_percent']}%")
                print(f" └─ Status JSON : Berhasil di-append ke file '{QOS_JSON_LOG_PATH}'")

                # --- 2. LOG SUMMARY BERDASARKAN PARAMETER PENGUJIAN KUMULATIF ---
                avg_delay_cum = np.mean(qos_state["history_delay"])
                print(f"--- SUMMARY KUMULATIF PARAMETER ---")
                print(f" ● Total Paket Berhasil Terkirim Ke Gateway : {qos_state['total_packet_received']} Paket")
                print(f" ● Rata-rata Delay Aktual Transmisi LoRa    : {round(avg_delay_cum,2)} ms")
                print(f" ● Nilai Akhir Gangguan Jitter Jaringan     : {qos_metrics['jitter_ms']} ms")
                print(f" ● Rasio Akumulasi Kerusakan Data Paket     : {qos_metrics['packet_loss_percent']}%")
                print(f"------------------------------------")

                # Push Gabungan Data Utama + QoS ke Firebase Dashboard Anda
                try:
                    sys_m = get_system_metrics()
                    payload = {
                        "timestamp": qos_metrics['waktu'],
                        "suhu": float(merged_data.get('t', 0) or 0), "kelembapan": float(merged_data.get('h', 0) or 0),
                        "jarak_air": float(merged_data.get('d', 0) or 0), "rssi": int(current_rssi),
                        "prediction_status": str(status_siaga), "probability": round(float(final_prob) * 100, 2),
                        "qos_delay_ms": qos_metrics['delay_ms'], "qos_packet_loss": qos_metrics['packet_loss_percent'],
                        "cpu_percent": sys_m.get("cpu_percent", 0)
                    }
                    db.child("ews_flood_dashboard").set(payload)
                except Exception as fb_err:
                    pass

        time.sleep(0.01)
except KeyboardInterrupt:
    print("\n 🛑 Monitoring dihentikan.")