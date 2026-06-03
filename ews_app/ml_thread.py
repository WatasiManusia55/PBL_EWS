# ml_thread.py
import threading
import queue
import time
import datetime
import os
import pandas as pd
from prediction_engine import PredictionEngine
from database import DatabaseManager
from firebase_client import FirebaseClient
from utils import format_rupiah
from config import PREDICTION_LOG_PATH, MIN_HISTORY_FOR_PREDICTION  # ← Tambahkan import ini

class MLThread(threading.Thread):

    def __init__(
        self,
        prediction_queue,
        sensor_data_queue,
        firebase_client=None
    ):
        super().__init__(daemon=True)

        self.prediction_queue = prediction_queue
        self.sensor_data_queue = sensor_data_queue

        self.engine = PredictionEngine()
        self.db = DatabaseManager()

        self.firebase = firebase_client

        self.running = True
        
    def run(self):
        print("🧠 ML Thread Started")
        
        while self.running:
            try:
                # Get prediction request from queue (non-blocking with timeout)
                try:
                    request = self.prediction_queue.get(timeout=0.1)
                except queue.Empty:
                    time.sleep(0.1)
                    continue
                
                sensor_dict = request['sensor_data']
                rssi = request['rssi']
                system_metrics = request['system_metrics']
                current_time = datetime.datetime.now()
                
                # Check if prediction is needed
                if not self.engine.can_predict(current_time):
                    continue
                
                # Convert and build features
                converted = self.engine.convert_sensor_data_for_prediction(sensor_dict)
                feature_row = self.engine.build_features_for_prediction(converted)
                
                # Check if enough history
                if len(self.engine.history) < MIN_HISTORY_FOR_PREDICTION:

                    current_history = len(self.engine.history)

                    print(
                        f"📊 Collecting history... "
                        f"{current_history}/{MIN_HISTORY_FOR_PREDICTION}"
                    )

                    prediction_result = {
                        "timestamp": converted["timestamp"],
                        "distance_to_water_m": float(
                            converted["RiverWaterLevel_m"]
                        ),
                        "water_height_m": 0.0,
                        "rf_prob": 0.0,
                        "final_prob": 0.0,
                        "threshold": float(self.engine.threshold),
                        "pred_alert": 0,
                        "status": "SIAGA 3",
                        "is_flooded": False,
                        "affected_area_ha": 0.0,
                        "affected_area_m2": 0,
                        "affected_kk": 0,
                        "bantuan_per_kk_idr": 0,
                        "total_budget_idr": 0,
                        "diagnosis":
                            f"Menunggu data historis "
                            f"({current_history}/{MIN_HISTORY_FOR_PREDICTION})"
                    }

                    self.firebase.update_prediction(
                        sensor_dict,
                        prediction_result,
                        rssi,
                        system_metrics
                    )

                    continue
                
                # Predict
                rf_prob, final_prob, pred_alert = self.engine.predict_flood(feature_row)
                distance_to_water_m = float(converted["RiverWaterLevel_m"])
                status_siaga = self.engine.get_siaga_status(pred_alert, distance_to_water_m)
                is_flooded = status_siaga in ("SIAGA 1", "SIAGA 2")
                
                # Calculate water height
                from config import JARAK_DASAR_SUNGAI_M
                tinggi_air_m = JARAK_DASAR_SUNGAI_M - distance_to_water_m
                tinggi_air_m = max(0.0, float(tinggi_air_m))
                
                # Estimate impact
                affected_area_ha = self.engine.estimate_affected_area_ha(status_siaga)
                affected_area_m2 = self.engine.ha_to_m2(affected_area_ha)
                affected_kk = self.engine.estimate_affected_kk(affected_area_ha)
                total_budget, bantuan_per_kk = self.engine.estimate_budget(affected_kk, status_siaga)
                
                # Diagnose
                diagnosis = self.engine.diagnose_flood_cause(feature_row, status_siaga)
                
                # Build result
                prediction_result = {
                    "timestamp":               converted["timestamp"],
                    "distance_to_water_m":     float(distance_to_water_m),
                    "water_height_m":          float(tinggi_air_m),
                    "rf_prob":                 float(rf_prob),
                    "final_prob":              float(final_prob),
                    "threshold":               float(self.engine.threshold),
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
                
                # Print results
                self._print_prediction_result(prediction_result)
                
                # Save to database
                self.db.save_prediction(prediction_result)
                
                # Save prediction log
                self._save_prediction_log(prediction_result)
                
                # Update Firebase
                self.firebase.update_prediction(
                    sensor_dict, prediction_result, rssi, system_metrics
                )
                
                # Send result back to main thread (optional)
                self.sensor_data_queue.put({
                    'prediction': prediction_result,
                    'sensor_data': sensor_dict,
                    'rssi': rssi
                })
                
                # Update prediction time
                self.engine.update_prediction_time(current_time)
                
                # Alert console
                self._print_alert(status_siaga)
                
            except Exception as e:
                print(f"❌ ML Thread Error: {e}")
                import traceback
                traceback.print_exc()  # ← Tambahkan ini untuk debug
                time.sleep(1)
                
    def _print_prediction_result(self, result):
        """Print formatted prediction result"""
        print("\n" + "=" * 50)
        print("🔮 FLOOD PREDICTION RESULT")
        print("=" * 50)
        print(f"📊 Status Siaga    : {result['status']}")
        print(f"🌊 Tinggi Air      : {round(result['water_height_m'], 2)} m")
        print(f"📏 Jarak ke Air    : {round(result['distance_to_water_m'], 3)} m (raw)")
        print(f"📈 Probabilitas    : {round(result['final_prob'] * 100, 2)}%")
        print(f"🏠 Luas Terdampak  : {result['affected_area_ha']} Ha ({result['affected_area_m2']} m²)")
        print(f"👨‍👩‍👧‍👦 KK Terdampak    : {result['affected_kk']} KK")
        print(f"💰 Total Bantuan   : {format_rupiah(result['total_budget_idr'])}")
        print(f"📋 Diagnosis       : {result['diagnosis']}")
        print("=" * 50)
        
    def _print_alert(self, status_siaga):
        """Print alert based on status"""
        if status_siaga == "SIAGA 1":
            print("\n🔴🔴🔴 FLOOD WARNING - DARURAT! 🔴🔴🔴")
            print("🚨 SEGERA EVAKUASI! 🚨")
        elif status_siaga == "SIAGA 2":
            print("\n🟠🟠🟠 EARLY WARNING - WASPADA! 🟠🟠🟠")
            print("⚠️ PERSIAPKAN EVAKUASI! ⚠️")
            
    def _save_prediction_log(self, result):
        """Append prediction result to CSV"""
        from utils import convert_numpy_types
        result = convert_numpy_types(result)
        file_exists = os.path.exists(PREDICTION_LOG_PATH)
        log_row = pd.DataFrame([result])
        log_row.to_csv(PREDICTION_LOG_PATH, mode="a", header=not file_exists, index=False)
        
    def stop(self):
        self.running = False