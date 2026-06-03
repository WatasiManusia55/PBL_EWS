# config.py
import os

# Model & Paths
MODEL_PATH = "flood_early_warning_rf_model.pkl"
PREDICTION_LOG_PATH = "flood_prediction_log.csv"

# Interval settings
SENSOR_INTERVAL_SECONDS = 30
SYSTEM_METRICS_INTERVAL = 30

# History buffer
MIN_HISTORY_FOR_PREDICTION = 60
MAX_HISTORY = 720

# Unit conversions
CM_TO_M_DIVISOR = 100.0

# Physical sensor config
THRESHOLD_SIAGA_1_M = 1.20
THRESHOLD_SIAGA_2_M = 1.50
JARAK_DASAR_SUNGAI_M = 2.0
SENSOR_MAX_VALID_CM = 210.0

# Impact estimation
TOTAL_AREA_HA = 6.0
TOTAL_KK = 35
KK_PER_HA = TOTAL_KK / TOTAL_AREA_HA
SIAGA_2_DAMPAK_PERSEN = 0.45
SIAGA_1_DAMPAK_PERSEN = 0.70

BANTUAN_PER_KK = {
    "SIAGA 2": 650_000,
    "SIAGA 1": 1_000_000,
}

# LoRa settings
FREQ = 915.0

# PostgreSQL
DB_HOST = "localhost"
DB_NAME = "ews_banjir"
DB_USER = "pi"
DB_PASSWORD = "ews"

# Firebase
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyBmgepsmVXP1ekfUl47RsllWl-BnjKkSno",
    "authDomain": "ews3-858da.firebaseapp.com",
    "databaseURL": "https://ews3-858da-default-rtdb.asia-southeast1.firebasedatabase.app/",
    "storageBucket": "ews3-858da.appspot.com"
}
FIREBASE_EMAIL = "ewsraspy@gmail.com"
FIREBASE_PASSWORD = "ewskelompok3"

# Export all variables untuk memudahkan import
__all__ = [
    'MODEL_PATH', 'PREDICTION_LOG_PATH', 'SENSOR_INTERVAL_SECONDS',
    'SYSTEM_METRICS_INTERVAL', 'MIN_HISTORY_FOR_PREDICTION', 'MAX_HISTORY',
    'CM_TO_M_DIVISOR', 'THRESHOLD_SIAGA_1_M', 'THRESHOLD_SIAGA_2_M',
    'JARAK_DASAR_SUNGAI_M', 'SENSOR_MAX_VALID_CM', 'TOTAL_AREA_HA',
    'TOTAL_KK', 'KK_PER_HA', 'SIAGA_2_DAMPAK_PERSEN', 'SIAGA_1_DAMPAK_PERSEN',
    'BANTUAN_PER_KK', 'FREQ', 'DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
    'FIREBASE_CONFIG', 'FIREBASE_EMAIL', 'FIREBASE_PASSWORD'
]