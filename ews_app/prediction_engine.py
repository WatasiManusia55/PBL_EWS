# prediction_engine.py
import os
import joblib
import pandas as pd
import numpy as np
import datetime
from collections import deque
from config import *
import math

class PredictionEngine:
    def __init__(self):
        self.rf = None
        self.features = []
        self.threshold = 0.5
        self.model_loaded = False
        self.history = deque(maxlen=MAX_HISTORY)
        self.last_prediction_time = None
        self._load_model()
        
    def _load_model(self):
        """Load Random Forest model"""
        if os.path.exists(MODEL_PATH):
            try:
                model_data = joblib.load(MODEL_PATH)
                self.rf = model_data["rf"]
                self.features = model_data["features"]
                self.threshold = float(model_data["threshold"])
                self.model_loaded = True
                print("✅ Random Forest Model Loaded Successfully")
                print(f"   Threshold : {self.threshold}")
                print(f"   Features  : {self.features}")
            except Exception as e:
                print(f"⚠️ Model loading error: {e}")
                print("   Running in rule-based mode only")
        else:
            print(f"⚠️ Model not found at {MODEL_PATH}")
            print("   Running in rule-based mode only")
            
    def convert_sensor_data_for_prediction(self, raw_data):
        """Convert sensor packet to model input format"""
        jarak_air_cm = raw_data.get("d", 0)
        if jarak_air_cm is None:
            jarak_air_cm = 0
        distance_m = float(jarak_air_cm) / CM_TO_M_DIVISOR

        return {
            "timestamp":            datetime.datetime.now(),
            "Temperature_C":        float(raw_data.get("t", 0) or 0),
            "Humidity_percent":     float(raw_data.get("h", 0) or 0),
            "SeaLevelPressure_hPa": float(raw_data.get("p", 1013) or 1013),
            "Precipitation_mm":     float(raw_data.get("rr", 0) or 0),
            "RiverWaterLevel_m":    float(distance_m)
        }
        
    def build_features_for_prediction(self, current_data):
        """Build features for ML based on history"""
        self.history.append(current_data)
        df_hist = pd.DataFrame(list(self.history))

        current_distance = float(current_data["RiverWaterLevel_m"])
        current_precipitation = float(current_data["Precipitation_mm"])

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
        
    def predict_flood(self, feature_row):
        """Predict flood via RF or rule-based fallback"""
        if not self.model_loaded or self.rf is None:
            jarak = float(feature_row.get("RiverWaterLevel_m", 10))
            if jarak <= THRESHOLD_SIAGA_1_M:
                return 0.95, 0.95, 1
            elif jarak <= THRESHOLD_SIAGA_2_M:
                return 0.7, 0.7, 1
            else:
                return 0.1, 0.1, 0

        try:
            X = pd.DataFrame([feature_row])
            X_model = X[self.features]
            rf_prob = float(self.rf.predict_proba(X_model)[:, 1][0])
            final_prob = float(rf_prob)
            pred_alert = int(final_prob >= self.threshold)
            return rf_prob, final_prob, pred_alert
        except Exception as e:
            print(f"⚠️ Prediction error: {e}")
            return 0.0, 0.0, 0
            
    def get_siaga_status(self, pred_alert, distance_to_water_m):
        """Determine siaga status: physical thresholds + ML early warning"""
        pred_alert = int(pred_alert) if not isinstance(pred_alert, int) else pred_alert
        distance_to_water_m = float(distance_to_water_m)

        if distance_to_water_m <= THRESHOLD_SIAGA_1_M:
            return "SIAGA 1"
        if distance_to_water_m <= THRESHOLD_SIAGA_2_M:
            return "SIAGA 2"
        if pred_alert == 1:
            return "SIAGA 2"
        return "SIAGA 3"
        
    def estimate_affected_area_ha(self, status_siaga):
        """Affected area in hectares based on siaga status"""
        if status_siaga == "SIAGA 1":
            persen = SIAGA_1_DAMPAK_PERSEN
        elif status_siaga == "SIAGA 2":
            persen = SIAGA_2_DAMPAK_PERSEN
        else:
            persen = 0.0
        return round(float(persen * TOTAL_AREA_HA), 2)
        
    def ha_to_m2(self, ha):
        return int(float(ha) * 10_000)
        
    def estimate_affected_kk(self, area_ha):
        kk = float(area_ha) * KK_PER_HA
        return min(int(round(kk)), TOTAL_KK)
        
    def estimate_budget(self, affected_kk, status_siaga):
        """Total budget = affected KK x aid per KK according to siaga"""
        bantuan = BANTUAN_PER_KK.get(status_siaga, 0)
        return int(int(affected_kk) * bantuan), int(bantuan)
        
    def diagnose_flood_cause(self, feature_row, status_siaga):
        """Diagnose flood cause based on sensor data"""
        if status_siaga == "SIAGA 3":
            return "Kondisi aman, pemantauan rutin."

        causes = []

        if float(feature_row.get("Rain_30min", 0)) >= 10:
            causes.append("Hujan lokal intensitas tinggi (30 menit terakhir)")
        if float(feature_row.get("Rain_1h", 0)) >= 20:
            causes.append("Hujan lokal lebat (1 jam terakhir)")
        if float(feature_row.get("Rain_3h", 0)) >= 30:
            causes.append("Akumulasi hujan tinggi (3 jam terakhir)")
        if float(feature_row.get("Rain_6h", 0)) >= 50:
            causes.append("Akumulasi hujan sangat tinggi (6 jam terakhir)")

        is_kiriman = (
            float(feature_row.get("WaterLevel_Change_1h", 0)) <= -0.15
            and float(feature_row.get("Rain_3h", 0)) < 10
        )
        if is_kiriman:
            causes.append("Kemungkinan banjir kiriman dari hulu")

        if float(feature_row.get("WaterLevel_Change_30min", 0)) <= -0.10:
            causes.append("Permukaan air naik cepat (30 menit terakhir)")
        if float(feature_row.get("WaterLevel_Change_3h", 0)) <= -0.30:
            causes.append("Kenaikan permukaan air signifikan (3 jam terakhir)")

        if float(feature_row.get("SeaLevelPressure_hPa", 1013)) <= 1005:
            causes.append("Tekanan udara rendah, indikasi cuaca buruk")

        if float(feature_row.get("RiverWaterLevel_m", 10)) <= THRESHOLD_SIAGA_1_M:
            causes.append("Air sudah mencapai permukaan jalan, banjir terkonfirmasi")

        if not causes:
            causes.append("Banjir terdeteksi, penyebab dominan belum teridentifikasi")

        return " | ".join(causes)
        
    def can_predict(self, current_time):
        """Check if enough time has passed since last prediction"""
        if self.last_prediction_time is not None:
            time_diff = (current_time - self.last_prediction_time).total_seconds()
            if time_diff < SENSOR_INTERVAL_SECONDS:
                return False
        return True
        
    def update_prediction_time(self, current_time):
        self.last_prediction_time = current_time