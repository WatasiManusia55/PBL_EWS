# firebase_client.py

import pyrebase
import datetime
import time

from config import (
    FIREBASE_CONFIG,
    FIREBASE_EMAIL,
    FIREBASE_PASSWORD
)

from utils import (
    convert_numpy_types,
    noise_label
)


class FirebaseClient:

    def __init__(self):

        self.firebase = pyrebase.initialize_app(FIREBASE_CONFIG)
        self.auth = self.firebase.auth()
        self.db = self.firebase.database()

        self.uid = None
        self.token = None
        self.token_expiry = 0

        self._login()

    # ==========================================================
    # AUTH
    # ==========================================================

    def _login(self):

        try:

            firebase_user = (
                self.auth.sign_in_with_email_and_password(
                    FIREBASE_EMAIL,
                    FIREBASE_PASSWORD
                )
            )

            self.token = firebase_user["idToken"]
            self.uid = firebase_user["localId"]

            self.token_expiry = time.time() + 3500

            print("🔥 Firebase Login Success")
            print(f"   UID: {self.uid}")

            return True

        except Exception as e:

            print("❌ Firebase Login Error:", e)
            return False

    def _refresh_token_if_needed(self):

        if time.time() >= self.token_expiry:

            print("🔄 Refreshing Firebase token...")
            return self._login()

        return True

    # ==========================================================
    # BUILD PAYLOAD
    # ==========================================================

    def _build_payload(
        self,
        sensor_data,
        prediction_result,
        rssi,
        system_metrics
    ):

        timestamp_str = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        sensor_data = convert_numpy_types(sensor_data or {})
        prediction_result = convert_numpy_types(
            prediction_result or {}
        )
        system_metrics = convert_numpy_types(
            system_metrics or {}
        )

        return {

            # ------------------------
            # SENSOR
            # ------------------------

            "timestamp": timestamp_str,

            "suhu":
                float(sensor_data.get("t", 0) or 0),

            "kelembapan":
                float(sensor_data.get("h", 0) or 0),

            "tekanan":
                float(sensor_data.get("p", 0) or 0),

            "jarak_air":
                float(sensor_data.get("d", 0) or 0),

            "flow":
                float(sensor_data.get("f", 0) or 0),

            "rain_total":
                float(sensor_data.get("rt", 0) or 0),

            "rain_rate":
                float(sensor_data.get("rr", 0) or 0),

            "float_level":
                float(sensor_data.get("lv", 0) or 0),

            "alert":
                str(sensor_data.get("al", "NORMAL")),

            "seq":
                int(sensor_data.get("sq", 0) or 0),

            "rssi":
                int(rssi),

            "status":
                "Monitoring",

            # ------------------------
            # ML
            # ------------------------

            "prediction_status":
                str(
                    prediction_result.get(
                        "status",
                        "COLLECTING_DATA"
                    )
                ),

            "is_flooded":
                bool(
                    prediction_result.get(
                        "is_flooded",
                        False
                    )
                ),

            "probability":
                round(
                    float(
                        prediction_result.get(
                            "final_prob",
                            0
                        )
                    ) * 100,
                    2
                ),

            "water_height_m":
                float(
                    prediction_result.get(
                        "water_height_m",
                        0
                    )
                ),

            "distance_to_water_m":
                float(
                    prediction_result.get(
                        "distance_to_water_m",
                        0
                    )
                ),

            "affected_area_ha":
                float(
                    prediction_result.get(
                        "affected_area_ha",
                        0
                    )
                ),

            "affected_kk":
                int(
                    prediction_result.get(
                        "affected_kk",
                        0
                    )
                ),

            "total_budget_idr":
                int(
                    prediction_result.get(
                        "total_budget_idr",
                        0
                    )
                ),

            "diagnosis":
                str(
                    prediction_result.get(
                        "diagnosis",
                        ""
                    )
                ),

            # ------------------------
            # SYSTEM
            # ------------------------

            "cpu_percent":
                system_metrics.get(
                    "cpu_percent",
                    0
                ),

            "memory_percent":
                system_metrics.get(
                    "memory_percent",
                    0
                ),

            "memory_used_mb":
                system_metrics.get(
                    "memory_used_mb",
                    0
                ),

            "memory_total_mb":
                system_metrics.get(
                    "memory_total_mb",
                    0
                ),

            "disk_percent":
                system_metrics.get(
                    "disk_percent",
                    0
                ),

            "disk_used_gb":
                system_metrics.get(
                    "disk_used_gb",
                    0
                ),

            "disk_total_gb":
                system_metrics.get(
                    "disk_total_gb",
                    0
                ),

            "load_avg_1min":
                system_metrics.get(
                    "load_avg_1min",
                    0
                ),

            "load_avg_5min":
                system_metrics.get(
                    "load_avg_5min",
                    0
                ),

            "load_avg_15min":
                system_metrics.get(
                    "load_avg_15min",
                    0
                ),

            "temperature_celsius":
                system_metrics.get(
                    "temperature_celsius"
                )
        }

    # ==========================================================
    # SENSOR ONLY
    # ==========================================================

    def update_sensor_only(
        self,
        sensor_data,
        rssi,
        system_metrics
    ):

        try:

            if not self._refresh_token_if_needed():
                return False

            payload = {

                "timestamp":
                    datetime.datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),

                "suhu":
                    float(sensor_data.get("t", 0) or 0),

                "kelembapan":
                    float(sensor_data.get("h", 0) or 0),

                "tekanan":
                    float(sensor_data.get("p", 0) or 0),

                "jarak_air":
                    float(sensor_data.get("d", 0) or 0),

                "flow":
                    float(sensor_data.get("f", 0) or 0),

                "rain_total":
                    float(sensor_data.get("rt", 0) or 0),

                "rain_rate":
                    float(sensor_data.get("rr", 0) or 0),

                "float_level":
                    float(sensor_data.get("lv", 0) or 0),

                "alert":
                    str(sensor_data.get("al", "NORMAL")),

                "seq":
                    int(sensor_data.get("sq", 0) or 0),

                "rssi":
                    int(rssi),

                "cpu_percent":
                    system_metrics.get("cpu_percent", 0),

                "memory_percent":
                    system_metrics.get("memory_percent", 0),

                "temperature_celsius":
                    system_metrics.get(
                        "temperature_celsius"
                    )
            }

            # update sebagian field saja
            self.db.child("node1") \
                .child("latest") \
                .child(self.uid) \
                .update(payload, self.token)

            return True

        except Exception as e:

            print(f"❌ Firebase Sensor Error: {e}")
            return False

    # ==========================================================
    # PREDICTION
    # ==========================================================

    def update_prediction(
        self,
        sensor_data,
        prediction_result,
        rssi,
        system_metrics
    ):

        try:

            if not self._refresh_token_if_needed():
                return False

            payload = self._build_payload(
                sensor_data,
                prediction_result,
                rssi,
                system_metrics
            )

            # latest
            self.db.child("node1") \
                .child("latest") \
                .child(self.uid) \
                .set(payload, self.token)

            # history
            self.db.child("node1") \
                .child("history") \
                .child(self.uid) \
                .push(payload, self.token)

            # monitoring
            self.db.child("system_monitoring") \
                .child(self.uid) \
                .set({

                    "timestamp":
                        payload["timestamp"],

                    **convert_numpy_types(
                        system_metrics
                    ),

                    "rssi":
                        int(rssi),

                    "noise_status":
                        noise_label(rssi)

                }, self.token)

            print(
                "☁️ Firebase Updated "
                "(sensor + prediction + metrics)"
            )

            return True

        except Exception as e:

            print(f"❌ Firebase Update Error: {e}")

            import traceback
            traceback.print_exc()

            return False