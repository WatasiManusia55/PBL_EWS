# main.py
import time
import datetime
import queue
import threading
from lora_receiver import LoRaReceiver
from database import DatabaseManager
from system_monitor import get_system_metrics
from ml_thread import MLThread
from utils import parse_packet, noise_label
from firebase_client import FirebaseClient
from warning_node import WarningNode

class EWSApplication:
    def __init__(self):
        self.lora = LoRaReceiver()
        self.db = DatabaseManager()

        # buat dulu firebase
        self.firebase = FirebaseClient()

        self.prediction_queue = queue.Queue()
        self.sensor_data_queue = queue.Queue()

        self.ml_thread = MLThread(
            self.prediction_queue,
            self.sensor_data_queue,
            self.firebase
        )

        self.running = True
        self.total_packet = 0
        self.last_wait_print = 0
        self.last_system_metrics = 0
        self.last_complete_data = {}
        self.system_metrics_interval = 30
        self.warning_node = WarningNode()
        self.last_warning_status = None
        
    def merge_with_last_data(self, data):
        """Merge partial packet with last complete data"""
        important_keys = ['t', 'h', 'p', 'd']
        is_complete = any(k in data for k in important_keys)
        
        from config import SENSOR_MAX_VALID_CM
        
        if is_complete:
            data = data.copy()
            if 'd' in data and data['d'] is not None:
                d_cm = round(float(data['d']) / 10, 1)
                if d_cm <= 0 or d_cm > SENSOR_MAX_VALID_CM:
                    print(f"⚠️ Jarak air di luar rentang wajar ({d_cm} cm) - diabaikan")
                    data.pop('d', None)
                else:
                    data['d'] = d_cm
            self.last_complete_data.update(data)
            return self.last_complete_data.copy()
        else:
            merged = self.last_complete_data.copy()
            merged.update(data)
            return merged
            
    def display_data(self, data, rssi, system_metrics):
        """Display received data"""
        self.total_packet += 1
        print("\n" + "═" * 70)
        print(f"📩 DATA #{self.total_packet}")
        print(f"🕒 Waktu : {datetime.datetime.now().strftime('%H:%M:%S')}")
        print(f"📶 RSSI  : {rssi} dBm ({noise_label(rssi)})")
        print(f"🌡️ Suhu  : {data.get('t', 'N/A')}")
        print(f"💧 Hum   : {data.get('h', 'N/A')}")
        print(f"🎯 Tekanan: {data.get('p', 'N/A')}")
        print(f"🌊 Jarak : {data.get('d', 'N/A')} cm (raw)")
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
        
    def run(self):
        """Main loop for receiving LoRa packets"""
        print("📡 Receiver Ready with Flood Prediction & System Monitoring")
        from config import JARAK_DASAR_SUNGAI_M
        print(f"   JARAK_DASAR_SUNGAI_M = {JARAK_DASAR_SUNGAI_M} m")
        print("-" * 70)
        
        # Start ML thread
        self.ml_thread.start()
        
        while self.running:
            try:
                packet = self.lora.receive(timeout=1.0)
                current_time = time.time()
                system_metrics = get_system_metrics()
                rssi_current = self.lora.get_live_rssi()
                
                # Save system metrics periodically
                if current_time - self.last_system_metrics >= self.system_metrics_interval:
                    self.db.save_system_metrics(rssi_current, system_metrics)
                    self.last_system_metrics = current_time
                
                if packet is not None:
                    raw_str = packet.decode("utf-8", errors="ignore")
                    data = parse_packet(raw_str)
                    
                    if data and len(data) > 0:
                        rssi = self.lora.get_last_rssi()
                        
                        # Merge partial -> full data
                        final_data = self.merge_with_last_data(data)
                        
                        # Save to sensor_log
                        self.db.save_sensor_data(final_data, rssi)
                        self.firebase.update_sensor_only(
                            final_data,
                            rssi,
                            system_metrics
                        )
                        
                        # Queue for prediction
                        self.prediction_queue.put({
                            'sensor_data': final_data,
                            'rssi': rssi,
                            'system_metrics': system_metrics
                        })
                        
                        # Display
                        self.display_data(final_data, rssi, system_metrics)
                        
                    else:
                        print("❌ Gagal parse packet")
                else:
                    now = time.time()
                    if now - self.last_wait_print >= 2:
                        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                              f"⌛ Waiting... | RSSI: {rssi_current} dBm | {noise_label(rssi_current)} | "
                              f"CPU: {system_metrics.get('cpu_percent', 0)}% | "
                              f"Mem: {system_metrics.get('memory_percent', 0)}%")
                        self.last_wait_print = now
                        
            except KeyboardInterrupt:
                print("\n🛑 STOP")
                break
            except Exception as e:
                print(f"❌ ERROR: {e}")
                time.sleep(1)
                
        self.stop()
        
    def stop(self):
        """Clean shutdown"""
        self.running = False
        self.ml_thread.stop()
        self.ml_thread.join(timeout=5)
        self.db.close()
        print("✅ Connections closed")

if __name__ == "__main__":
    app = EWSApplication()
    app.run()
