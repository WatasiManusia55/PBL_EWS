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
import numpy as np
import statistics
import matplotlib.pyplot as plt

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
# QOS TESTER CLASS (TAMBAHKAN INI)
# ===============================================================
class LoRaQoSTester:
    def __init__(self, test_duration_seconds=300, test_name="qos_test"):
        self.test_duration = test_duration_seconds
        self.test_name = test_name
        self.packet_log = []
        self.packet_sent = 0
        self.packet_received = 0
        self.start_time = None
        self.end_time = None
        self.delays = deque(maxlen=1000)
        self.packet_sizes = deque(maxlen=1000)
        self.receive_times = deque(maxlen=1000)
        self.last_seq = -1
        self.missing_seqs = []
    
    def calculate_delay(self, send_time_str, receive_time):
        try:
            if isinstance(send_time_str, str):
                send_time = datetime.datetime.strptime(send_time_str, "%Y-%m-%d %H:%M:%S")
            else:
                send_time = send_time_str
            delay_seconds = (receive_time - send_time).total_seconds()
            delay_ms = delay_seconds * 1000
            return max(0, delay_ms)
        except Exception as e:
            return None
    
    def calculate_throughput(self, total_bytes, time_seconds):
        if time_seconds <= 0:
            return 0, 0
        total_bits = total_bytes * 8
        throughput_bps = total_bits / time_seconds
        throughput_kbps = throughput_bps / 1000
        return throughput_bps, throughput_kbps
    
    def calculate_packet_loss(self, packets_sent, packets_received):
        if packets_sent == 0:
            return 0
        packet_loss = ((packets_sent - packets_received) / packets_sent) * 100
        return packet_loss
    
    def calculate_jitter(self, delays):
        if len(delays) < 2:
            return 0
        total_variation = 0
        for i in range(1, len(delays)):
            total_variation += abs(delays[i] - delays[i-1])
        jitter_ms = total_variation / (len(delays) - 1)
        return jitter_ms
    
    def log_packet(self, seq_num, packet_size_bytes, send_timestamp, receive_time, delay_ms):
        self.packet_log.append({
            "seq": seq_num,
            "size_bytes": packet_size_bytes,
            "send_time": send_timestamp,
            "receive_time": receive_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            "delay_ms": delay_ms
        })
        self.delays.append(delay_ms)
        self.packet_sizes.append(packet_size_bytes)
        self.receive_times.append(receive_time)
        self.packet_received += 1
        
        if self.last_seq != -1:
            expected_seq = self.last_seq + 1
            if seq_num > expected_seq:
                for missing in range(expected_seq, seq_num):
                    self.missing_seqs.append(missing)
        self.last_seq = seq_num
    
    def update_packet_sent(self, max_seq):
        if max_seq > 0:
            self.packet_sent = max_seq
    
    def parse_qos_packet(self, raw_str):
        raw_str = raw_str.strip()
        if not raw_str:
            return None
        
        if raw_str.startswith('":'):
            raw_str = '{' + raw_str[2:] if not raw_str.startswith('{') else raw_str
        if raw_str.startswith(':'):
            raw_str = '{"t"' + raw_str
        if not raw_str.startswith('{'):
            raw_str = '{' + raw_str
        if not raw_str.endswith('}'):
            raw_str += '}'
        
        raw_str = re.sub(r'([a-zA-Z]+):', r'"\1":', raw_str)
        raw_str = raw_str.replace("'", '"')
        raw_str = re.sub(r'[^\x20-\x7E]', '', raw_str)
        
        try:
            return json.loads(raw_str)
        except:
            try:
                data = {}
                pairs = re.findall(r'"?([a-zA-Z]+)"?\s*:\s*([0-9.]+)', raw_str)
                for key, value in pairs:
                    if '.' in value:
                        data[key] = float(value)
                    else:
                        data[key] = int(value)
                return data if data else None
            except:
                return None
    
    def run_qos_test(self, lora_receiver, duration_seconds=None):
        if duration_seconds:
            self.test_duration = duration_seconds
        
        print("\n" + "="*70)
        print("📡 QoS TESTING STARTED")
        print(f"⏱️  Duration: {self.test_duration} seconds")
        print("="*70)
        
        self.start_time = time.time()
        self.end_time = self.start_time + self.test_duration
        
        self.packet_log = []
        self.delays.clear()
        self.packet_sizes.clear()
        self.receive_times.clear()
        self.missing_seqs = []
        self.packet_received = 0
        self.packet_sent = 0
        self.last_seq = -1
        
        try:
            while time.time() < self.end_time:
                packet = lora_receiver.receive(timeout=0.5)
                
                if packet is not None:
                    raw_str = packet.decode("utf-8", errors="ignore")
                    data = self.parse_qos_packet(raw_str)
                    
                    if data and 'sq' in data:
                        receive_time = datetime.datetime.now()
                        packet_size = len(raw_str.encode('utf-8'))
                        send_timestamp = data.get('ts', receive_time.strftime("%Y-%m-%d %H:%M:%S"))
                        delay_ms = self.calculate_delay(send_timestamp, receive_time)
                        
                        if delay_ms is not None:
                            self.log_packet(
                                seq_num=data['sq'],
                                packet_size_bytes=packet_size,
                                send_timestamp=send_timestamp,
                                receive_time=receive_time,
                                delay_ms=delay_ms
                            )
                            if data['sq'] > self.packet_sent:
                                self.packet_sent = data['sq']
                            
                            if self.packet_received % 10 == 0:
                                print(f"📊 Progress: {self.packet_received} packets received")
                
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n⚠️ QoS test interrupted")
        
        print("\n" + "="*70)
        print("📡 QoS TESTING COMPLETED")
        print("="*70)
        
        return self.generate_qos_report()
    
    def generate_qos_report(self):
        if self.packet_received == 0:
            print("❌ No packets received during QoS test")
            return None
        
        total_time_seconds = self.test_duration
        
        delays_list = list(self.delays)
        avg_delay_ms = statistics.mean(delays_list) if delays_list else 0
        min_delay_ms = min(delays_list) if delays_list else 0
        max_delay_ms = max(delays_list) if delays_list else 0
        std_delay_ms = statistics.stdev(delays_list) if len(delays_list) > 1 else 0
        
        packet_loss_percent = self.calculate_packet_loss(self.packet_sent, self.packet_received)
        
        total_bytes = sum(self.packet_sizes)
        throughput_bps, throughput_kbps = self.calculate_throughput(total_bytes, total_time_seconds)
        
        jitter_ms = self.calculate_jitter(delays_list)
        
        pdr_percent = ((self.packet_received / self.packet_sent) * 100) if self.packet_sent > 0 else 0
        
        qos_rating = self.evaluate_qos_rating(avg_delay_ms, packet_loss_percent, jitter_ms, throughput_kbps)
        
        report = {
            "test_info": {
                "test_name": self.test_name,
                "test_duration_seconds": self.test_duration,
                "start_time": datetime.datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": datetime.datetime.fromtimestamp(self.end_time).strftime("%Y-%m-%d %H:%M:%S"),
                "total_packets_sent": self.packet_sent,
                "total_packets_received": self.packet_received,
                "missing_packets": len(self.missing_seqs),
                "missing_sequences": self.missing_seqs[:20]
            },
            "delay": {
                "average_ms": round(avg_delay_ms, 3),
                "minimum_ms": round(min_delay_ms, 3),
                "maximum_ms": round(max_delay_ms, 3),
                "std_deviation_ms": round(std_delay_ms, 3),
                "formula": "Delay = Waktu Diterima - Waktu Dikirim (RFC 2679)"
            },
            "packet_loss": {
                "percentage": round(packet_loss_percent, 3),
                "formula": "Packet Loss(%) = (Paket Dikirim - Paket Diterima)/Paket Dikirim × 100%"
            },
            "throughput": {
                "bps": round(throughput_bps, 2),
                "kbps": round(throughput_kbps, 2),
                "total_bytes": total_bytes,
                "total_bits": total_bytes * 8,
                "formula": "Throughput = Jumlah Data / Waktu Pengiriman"
            },
            "jitter": {
                "average_ms": round(jitter_ms, 3),
                "formula": "Jitter = Σ|Delay_i - Delay_(i-1)| / (n-1) (RFC 3550)"
            },
            "pdr": {
                "percentage": round(pdr_percent, 3)
            },
            "qos_rating": qos_rating
        }
        
        return report
    
    def evaluate_qos_rating(self, avg_delay_ms, packet_loss_percent, jitter_ms, throughput_kbps):
        score = 0
        
        if avg_delay_ms <= 150:
            score += 4
        elif avg_delay_ms <= 300:
            score += 3
        elif avg_delay_ms <= 450:
            score += 2
        else:
            score += 1
        
        if packet_loss_percent <= 1:
            score += 4
        elif packet_loss_percent <= 3:
            score += 3
        elif packet_loss_percent <= 5:
            score += 2
        else:
            score += 1
        
        if jitter_ms <= 20:
            score += 4
        elif jitter_ms <= 50:
            score += 3
        elif jitter_ms <= 100:
            score += 2
        else:
            score += 1
        
        if throughput_kbps >= 100:
            score += 4
        elif throughput_kbps >= 50:
            score += 3
        elif throughput_kbps >= 10:
            score += 2
        else:
            score += 1
        
        if score >= 14:
            return {"rating": "Excellent (Sangat Baik)", "score": score, "description": "Kualitas komunikasi sangat baik untuk real-time monitoring"}
        elif score >= 11:
            return {"rating": "Good (Baik)", "score": score, "description": "Kualitas komunikasi baik, layak untuk EWS"}
        elif score >= 8:
            return {"rating": "Fair (Cukup)", "score": score, "description": "Kualitas komunikasi cukup, perlu optimasi"}
        else:
            return {"rating": "Poor (Buruk)", "score": score, "description": "Kualitas komunikasi buruk, perlu perbaikan"}
    
    def export_qos_report(self, report):
        if report is None:
            return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        summary_data = {
            "Parameter": ["Average Delay", "Min Delay", "Max Delay", "Packet Loss", "Throughput", "Jitter", "PDR"],
            "Nilai": [
                report["delay"]["average_ms"],
                report["delay"]["minimum_ms"],
                report["delay"]["maximum_ms"],
                report["packet_loss"]["percentage"],
                report["throughput"]["kbps"],
                report["jitter"]["average_ms"],
                report["pdr"]["percentage"]
            ],
            "Satuan": ["ms", "ms", "ms", "%", "kbps", "ms", "%"]
        }
        
        df = pd.DataFrame(summary_data)
        csv_file = f"qos_report_{timestamp}.csv"
        df.to_csv(csv_file, index=False)
        print(f"📁 QoS report exported to {csv_file}")
        
        if self.packet_log:
            df_details = pd.DataFrame(self.packet_log)
            details_file = f"qos_packet_details_{timestamp}.csv"
            df_details.to_csv(details_file, index=False)
            print(f"📁 Packet details exported to {details_file}")
    
    def print_qos_report(self, report):
        if report is None:
            return
        
        print("\n" + "="*70)
        print("📡 QUALITY OF SERVICE (QoS) TEST REPORT")
        print("="*70)
        
        print("\n📋 TEST INFORMATION")
        print("-"*50)
        print(f"  Test Name           : {report['test_info']['test_name']}")
        print(f"  Test Duration       : {report['test_info']['test_duration_seconds']} seconds")
        print(f"  Total Packets Sent  : {report['test_info']['total_packets_sent']}")
        print(f"  Total Packets Recv  : {report['test_info']['total_packets_received']}")
        print(f"  Missing Packets     : {report['test_info']['missing_packets']}")
        
        print("\n⏱️ DELAY (RFC 2679)")
        print("-"*50)
        print(f"  Average Delay       : {report['delay']['average_ms']} ms")
        print(f"  Minimum Delay       : {report['delay']['minimum_ms']} ms")
        print(f"  Maximum Delay       : {report['delay']['maximum_ms']} ms")
        
        print("\n📦 PACKET LOSS")
        print("-"*50)
        print(f"  Packet Loss         : {report['packet_loss']['percentage']} %")
        
        print("\n🚀 THROUGHPUT")
        print("-"*50)
        print(f"  Throughput          : {report['throughput']['kbps']} kbps")
        print(f"  Total Data Transfer : {report['throughput']['total_bytes']} bytes")
        
        print("\n🔄 JITTER (RFC 3550)")
        print("-"*50)
        print(f"  Average Jitter      : {report['jitter']['average_ms']} ms")
        
        print("\n⭐ QoS RATING")
        print("-"*50)
        print(f"  Rating              : {report['qos_rating']['rating']}")
        print(f"  Score               : {report['qos_rating']['score']}/16")
        print(f"  Description         : {report['qos_rating']['description']}")
        
        print("\n" + "="*70)


# ===============================================================
# FUNGSI UNTUK MENJALANKAN QoS TEST
# ===============================================================
def run_qos_test_integration(lora_receiver, duration_seconds=300):
    """
    Fungsi untuk menjalankan QoS test dari sistem utama
    """
    qos_tester = LoRaQoSTester(
        test_duration_seconds=duration_seconds,
        test_name=f"lora_qos_test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    
    report = qos_tester.run_qos_test(lora_receiver, duration_seconds)
    
    if report:
        qos_tester.print_qos_report(report)
        qos_tester.export_qos_report(report)
        return report
    
    return None


def qos_test_menu():
    """
    Menu interaktif untuk menjalankan QoS testing
    """
    print("\n" + "="*70)
    print("📡 LORA QoS TESTING MENU")
    print("="*70)
    print("1. Quick Test (1 menit)")
    print("2. Standard Test (5 menit)")
    print("3. Extended Test (15 menit)")
    print("4. Custom Duration")
    print("5. Cancel")
    
    choice = input("\nPilih opsi (1-5): ").strip()
    
    durations = {'1': 60, '2': 300, '3': 900}
    
    if choice in durations:
        return durations[choice]
    elif choice == '4':
        try:
            minutes = int(input("Masukkan durasi (menit): "))
            return minutes * 60
        except:
            print("Input tidak valid, menggunakan default 5 menit")
            return 300
    elif choice == '5':
        return None
    else:
        print("Pilihan tidak valid, menggunakan default 5 menit")
        return 300


# ===============================================================
# POSTGRESQL (LANJUTAN KODE ANDA)
# ===============================================================
# ... (sambungkan dengan kode PostgreSQL, Firebase, LoRa Anda yang sudah ada)
# ... (sampai dengan bagian main loop)


# ===============================================================
# MAIN LOOP WITH QoS TESTING (GANTI MAIN LOOP ANDA DENGAN INI)
# ===============================================================
print("📡 Receiver Ready with Flood Prediction & QoS Testing")
print("-" * 70)

# Tambahkan variabel untuk tracking QoS test
last_qos_test_time = 0
QOS_TEST_INTERVAL = 3600  # Jalankan QoS test setiap 1 jam (3600 detik)
# Set ke 0 dulu agar tidak auto run, bisa diaktifkan nanti
AUTO_QOS_ENABLED = False  # Matikan auto QoS dulu, nanti bisa diaktifkan

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
                
                # Simpan ke database
                simpan_postgresql(final_data, rssi)
                
                # Proses prediksi banjir
                prediction_result = process_prediction(final_data, rssi)
                
                # Update Firebase dengan data sensor DAN prediksi
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
            
            # ===================================================
            # Auto QoS Test (optional, matikan dulu)
            # ===================================================
            if AUTO_QOS_ENABLED and now - last_qos_test_time >= QOS_TEST_INTERVAL:
                print("\n" + "="*70)
                print("🔄 Auto QoS Test Started")
                print("="*70)
                
                qos_report = run_qos_test_integration(rfm9x, duration_seconds=300)
                
                if qos_report:
                    print("✅ QoS Test Completed Successfully")
                
                last_qos_test_time = now
                
    except KeyboardInterrupt:
        print("\n" + "="*70)
        print("🛑 System Stopped by User")
        print("="*70)
        
        # Tanya apakah ingin menjalankan QoS test sebelum keluar
        response = input("\n📡 Run QoS Test before exit? (y/n): ").strip().lower()
        if response == 'y':
            duration = qos_test_menu()
            if duration:
                run_qos_test_integration(rfm9x, duration_seconds=duration)
        
        break
    except Exception as e:
        print(f"❌ ERROR: {e}")
        time.sleep(1)

cur.close()
conn.close()
print("✅ Connections closed")