# database.py
import psycopg2
import datetime
from sqlalchemy import create_engine
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.cur = None
        self.engine = None
        self.connect()
        
    def connect(self):
        """Establish database connections"""
        self.conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        self.conn.autocommit = True
        self.cur = self.conn.cursor()
        self.engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")
        self._create_tables()
        print("✅ PostgreSQL Connected")
        
    def _create_tables(self):
        """Create tables if not exists"""
        self.cur.execute("""
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
        
        self.cur.execute("""
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
        
        try:
            self.cur.execute("ALTER TABLE flood_prediction ADD COLUMN IF NOT EXISTS water_height_m REAL;")
        except Exception:
            pass
            
        self.cur.execute("""
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
        print("🛢 Tables Ready")
        
    def save_sensor_data(self, data, rssi):
        """Save sensor data to sensor_log table"""
        try:
            self.cur.execute("""
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
            print("🛢 PostgreSQL OK")
        except Exception as e:
            print(f"❌ PostgreSQL ERROR: {e}")
            
    def save_prediction(self, prediction_result):
        """Save prediction result to flood_prediction table"""
        try:
            self.cur.execute("""
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
            print("🛢 Prediction saved to PostgreSQL")
        except Exception as e:
            print(f"❌ DB Save Error: {e}")
            
    def save_system_metrics(self, rssi, system_metrics):
        """Save system metrics to database"""
        from utils import noise_label
        try:
            self.cur.execute("""
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
            print("🛢 System metrics saved to PostgreSQL")
        except Exception as e:
            print(f"❌ DB Save Metrics Error: {e}")
            
    def close(self):
        """Close database connections"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()