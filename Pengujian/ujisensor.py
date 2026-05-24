#!/usr/bin/env python3
"""
QoS TESTING MODULE FOR LoRA COMMUNICATION
Based on ETSI TIPHON and RFC standards
"""

import time
import json
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import deque
import statistics

class LoRaQoSTester:
    def __init__(self, test_duration_seconds=300, test_name="qos_test"):
        """
        Inisialisasi QoS Tester
        
        Args:
            test_duration_seconds: Durasi pengujian dalam detik (default 5 menit)
            test_name: Nama file untuk menyimpan hasil
        """
        self.test_duration = test_duration_seconds
        self.test_name = test_name
        
        # Buffer untuk menyimpan data pengujian
        self.packet_log = []  # Menyimpan setiap paket yang diterima
        self.packet_sent = 0  # Total paket yang dikirim (dari seq number)
        self.packet_received = 0
        self.start_time = None
        self.end_time = None
        
        # Queue untuk menyimpan data real-time
        self.delays = deque(maxlen=1000)
        self.packet_sizes = deque(maxlen=1000)
        self.receive_times = deque(maxlen=1000)
        
        # Stats
        self.last_seq = -1
        self.missing_seqs = []
        
    def calculate_delay(self, send_time_str, receive_time):
        """
        Menghitung delay (one-way delay berdasarkan RFC 2679)
        
        Rumus: Delay = Waktu Diterima - Waktu Dikirim
        
        Args:
            send_time_str: String timestamp dari pengirim
            receive_time: Datetime waktu diterima
        
        Returns:
            delay_ms: Delay dalam milidetik
        """
        try:
            # Parse timestamp dari pengirim
            if isinstance(send_time_str, str):
                send_time = datetime.datetime.strptime(send_time_str, "%Y-%m-%d %H:%M:%S")
            else:
                send_time = send_time_str
            
            # Hitung delay dalam detik
            delay_seconds = (receive_time - send_time).total_seconds()
            delay_ms = delay_seconds * 1000
            
            return max(0, delay_ms)  # Delay minimal 0
        except Exception as e:
            print(f"Error calculating delay: {e}")
            return None
    
    def calculate_throughput(self, total_bytes, time_seconds):
        """
        Menghitung throughput
        
        Rumus: Throughput = Jumlah Data / Waktu Pengiriman
        
        Args:
            total_bytes: Total data yang berhasil dikirim (bytes)
            time_seconds: Total waktu transmisi (detik)
        
        Returns:
            throughput_bps: Throughput dalam bps (bits per second)
            throughput_kbps: Throughput dalam kbps
        """
        if time_seconds <= 0:
            return 0, 0
        
        total_bits = total_bytes * 8
        throughput_bps = total_bits / time_seconds
        throughput_kbps = throughput_bps / 1000
        
        return throughput_bps, throughput_kbps
    
    def calculate_packet_loss(self, packets_sent, packets_received):
        """
        Menghitung packet loss
        
        Rumus: Packet Loss(%) = (Jumlah Paket Dikirim - Jumlah Paket Diterima) / Jumlah Paket Dikirim × 100%
        
        Args:
            packets_sent: Total paket yang dikirim
            packets_received: Total paket yang diterima
        
        Returns:
            packet_loss_percent: Persentase packet loss
        """
        if packets_sent == 0:
            return 0
        
        packet_loss = ((packets_sent - packets_received) / packets_sent) * 100
        return packet_loss
    
    def calculate_jitter(self, delays):
        """
        Menghitung jitter (interarrival jitter berdasarkan RFC 3550)
        
        Rumus: Jitter = Σ|Delay_i - Delay_(i-1)| / (n-1)
        
        Args:
            delays: List of delay values dalam ms
        
        Returns:
            jitter_ms: Jitter dalam milidetik
        """
        if len(delays) < 2:
            return 0
        
        total_variation = 0
        for i in range(1, len(delays)):
            total_variation += abs(delays[i] - delays[i-1])
        
        jitter_ms = total_variation / (len(delays) - 1)
        return jitter_ms
    
    def log_packet(self, seq_num, packet_size_bytes, send_timestamp, receive_time, delay_ms):
        """
        Mencatat setiap paket yang diterima untuk analisis
        
        Args:
            seq_num: Sequence number paket
            packet_size_bytes: Ukuran paket dalam bytes
            send_timestamp: Timestamp dari pengirim
            receive_time: Waktu paket diterima
            delay_ms: Delay paket dalam ms
        """
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
        
        # Cek paket yang hilang (jika seq number loncat)
        if self.last_seq != -1:
            expected_seq = self.last_seq + 1
            if seq_num > expected_seq:
                for missing in range(expected_seq, seq_num):
                    self.missing_seqs.append(missing)
        
        self.last_seq = seq_num
    
    def update_packet_sent(self, max_seq):
        """
        Update jumlah paket yang dikirim berdasarkan sequence number tertinggi
        
        Args:
            max_seq: Sequence number tertinggi yang diterima
        """
        # Asumsikan sequence number dimulai dari 1 atau 0
        if max_seq > 0:
            self.packet_sent = max_seq
    
    def run_qos_test(self, lora_receiver, duration_seconds=None):
        """
        Menjalankan pengujian QoS secara real-time
        
        Args:
            lora_receiver: Objek LoRa receiver
            duration_seconds: Durasi pengujian (override default)
        
        Returns:
            qos_report: Dictionary hasil pengujian QoS
        """
        if duration_seconds:
            self.test_duration = duration_seconds
        
        print("\n" + "="*70)
        print("📡 QoS TESTING STARTED")
        print(f"⏱️  Duration: {self.test_duration} seconds")
        print("="*70)
        
        self.start_time = time.time()
        self.end_time = self.start_time + self.test_duration
        
        # Reset data
        self.packet_log = []
        self.delays.clear()
        self.packet_sizes.clear()
        self.receive_times.clear()
        self.missing_seqs = []
        self.packet_received = 0
        self.packet_sent = 0
        self.last_seq = -1
        
        # Jalankan pengujian
        try:
            while time.time() < self.end_time:
                packet = lora_receiver.receive(timeout=0.5)
                
                if packet is not None:
                    raw_str = packet.decode("utf-8", errors="ignore")
                    data = self.parse_qos_packet(raw_str)
                    
                    if data and 'sq' in data:
                        receive_time = datetime.datetime.now()
                        
                        # Estimasi ukuran paket (dalam bytes)
                        packet_size = len(raw_str.encode('utf-8'))
                        
                        # Dapatkan timestamp pengirim (jika ada)
                        send_timestamp = data.get('ts', receive_time.strftime("%Y-%m-%d %H:%M:%S"))
                        
                        # Hitung delay
                        delay_ms = self.calculate_delay(send_timestamp, receive_time)
                        
                        if delay_ms is not None:
                            self.log_packet(
                                seq_num=data['sq'],
                                packet_size_bytes=packet_size,
                                send_timestamp=send_timestamp,
                                receive_time=receive_time,
                                delay_ms=delay_ms
                            )
                            
                            # Update packet sent berdasarkan seq tertinggi
                            if data['sq'] > self.packet_sent:
                                self.packet_sent = data['sq']
                            
                            # Tampilkan progress setiap 10 paket
                            if self.packet_received % 10 == 0:
                                print(f"📊 Progress: {self.packet_received} packets received")
                
                # Tampilkan waktu tersisa setiap 30 detik
                remaining = self.end_time - time.time()
                if int(remaining) % 30 == 0 and remaining > 0:
                    print(f"⏰ Time remaining: {int(remaining)} seconds")
                
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n⚠️ QoS test interrupted by user")
        
        print("\n" + "="*70)
        print("📡 QoS TESTING COMPLETED")
        print("="*70)
        
        return self.generate_qos_report()
    
    def parse_qos_packet(self, raw_str):
        """
        Parse packet untuk QoS testing
        """
        import re
        
        raw_str = raw_str.strip()
        if not raw_str:
            return None
        
        # Handle various packet formats
        if raw_str.startswith('":'):
            raw_str = '{' + raw_str[2:] if not raw_str.startswith('{') else raw_str
        
        if raw_str.startswith(':'):
            raw_str = '{"t"' + raw_str
        
        if not raw_str.startswith('{'):
            raw_str = '{' + raw_str
        
        if not raw_str.endswith('}'):
            raw_str += '}'
        
        # Fix keys without quotes
        raw_str = re.sub(r'([a-zA-Z]+):', r'"\1":', raw_str)
        raw_str = raw_str.replace("'", '"')
        raw_str = re.sub(r'[^\x20-\x7E]', '', raw_str)
        
        try:
            return json.loads(raw_str)
        except:
            # Manual extraction
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
    
    def generate_qos_report(self):
        """
        Menghasilkan laporan QoS berdasarkan data yang terkumpul
        
        Returns:
            report: Dictionary dengan semua metrik QoS
        """
        if self.packet_received == 0:
            print("❌ No packets received during QoS test")
            return None
        
        # Hitung total waktu transmisi
        total_time_seconds = self.test_duration
        
        # 1. Hitung Delay Statistics
        delays_list = list(self.delays)
        avg_delay_ms = statistics.mean(delays_list) if delays_list else 0
        min_delay_ms = min(delays_list) if delays_list else 0
        max_delay_ms = max(delays_list) if delays_list else 0
        std_delay_ms = statistics.stdev(delays_list) if len(delays_list) > 1 else 0
        
        # 2. Hitung Packet Loss
        packet_loss_percent = self.calculate_packet_loss(self.packet_sent, self.packet_received)
        
        # 3. Hitung Throughput
        total_bytes = sum(self.packet_sizes)
        throughput_bps, throughput_kbps = self.calculate_throughput(total_bytes, total_time_seconds)
        
        # 4. Hitung Jitter
        jitter_ms = self.calculate_jitter(delays_list)
        
        # 5. Hitung Packet Delivery Ratio (PDR)
        pdr_percent = ((self.packet_received / self.packet_sent) * 100) if self.packet_sent > 0 else 0
        
        # 6. Bandingkan dengan standar QoS (ETSI TIPHON)
        qos_rating = self.evaluate_qos_rating(
            avg_delay_ms, packet_loss_percent, jitter_ms, throughput_kbps
        )
        
        # Buat laporan
        report = {
            "test_info": {
                "test_name": self.test_name,
                "test_duration_seconds": self.test_duration,
                "start_time": datetime.datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": datetime.datetime.fromtimestamp(self.end_time).strftime("%Y-%m-%d %H:%M:%S"),
                "total_packets_sent": self.packet_sent,
                "total_packets_received": self.packet_received,
                "missing_packets": len(self.missing_seqs),
                "missing_sequences": self.missing_seqs[:20]  # Show first 20 missing
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
                "formula": "Packet Loss(%) = (Paket Dikirim - Paket Diterima)/Paket Dikirim × 100%",
                "standard": "ETSI TIPHON"
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
                "formula": "Jitter = Σ|Delay_i - Delay_(i-1)| / (n-1) (RFC 3550)",
                "standard": "RFC 3550 Interarrival Jitter"
            },
            "pdr": {
                "percentage": round(pdr_percent, 3)
            },
            "qos_rating": qos_rating
        }
        
        return report
    
    def evaluate_qos_rating(self, avg_delay_ms, packet_loss_percent, jitter_ms, throughput_kbps):
        """
        Mengevaluasi rating QoS berdasarkan standar ETSI TIPHON
        
        Returns:
            rating: String rating QoS (Excellent, Good, Fair, Poor)
        """
        score = 0
        
        # Delay threshold (ETSI TIPHON untuk real-time service)
        if avg_delay_ms <= 150:
            score += 4
        elif avg_delay_ms <= 300:
            score += 3
        elif avg_delay_ms <= 450:
            score += 2
        else:
            score += 1
        
        # Packet Loss threshold
        if packet_loss_percent <= 1:
            score += 4
        elif packet_loss_percent <= 3:
            score += 3
        elif packet_loss_percent <= 5:
            score += 2
        else:
            score += 1
        
        # Jitter threshold
        if jitter_ms <= 20:
            score += 4
        elif jitter_ms <= 50:
            score += 3
        elif jitter_ms <= 100:
            score += 2
        else:
            score += 1
        
        # Throughput threshold
        if throughput_kbps >= 100:
            score += 4
        elif throughput_kbps >= 50:
            score += 3
        elif throughput_kbps >= 10:
            score += 2
        else:
            score += 1
        
        # Rating classification
        if score >= 14:
            return {
                "rating": "Excellent (Sangat Baik)",
                "score": score,
                "description": "Kualitas komunikasi sangat baik untuk real-time monitoring"
            }
        elif score >= 11:
            return {
                "rating": "Good (Baik)",
                "score": score,
                "description": "Kualitas komunikasi baik, layak untuk EWS"
            }
        elif score >= 8:
            return {
                "rating": "Fair (Cukup)",
                "score": score,
                "description": "Kualitas komunikasi cukup, perlu optimasi"
            }
        else:
            return {
                "rating": "Poor (Buruk)",
                "score": score,
                "description": "Kualitas komunikasi buruk, perlu perbaikan"
            }
    
    def export_qos_report(self, report, format='csv'):
        """
        Mengekspor laporan QoS ke file
        
        Args:
            report: Dictionary hasil laporan QoS
            format: Format ekspor ('csv' atau 'json')
        """
        if report is None:
            return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == 'csv':
            # Export summary
            summary_data = {
                "Parameter": [],
                "Nilai": [],
                "Satuan": [],
                "Standar": []
            }
            
            # Delay
            summary_data["Parameter"].append("Average Delay")
            summary_data["Nilai"].append(report["delay"]["average_ms"])
            summary_data["Satuan"].append("ms")
            summary_data["Standar"].append("RFC 2679")
            
            summary_data["Parameter"].append("Min Delay")
            summary_data["Nilai"].append(report["delay"]["minimum_ms"])
            summary_data["Satuan"].append("ms")
            summary_data["Standar"].append("RFC 2679")
            
            summary_data["Parameter"].append("Max Delay")
            summary_data["Nilai"].append(report["delay"]["maximum_ms"])
            summary_data["Satuan"].append("ms")
            summary_data["Standar"].append("RFC 2679")
            
            # Packet Loss
            summary_data["Parameter"].append("Packet Loss")
            summary_data["Nilai"].append(report["packet_loss"]["percentage"])
            summary_data["Satuan"].append("%")
            summary_data["Standar"].append("ETSI TIPHON")
            
            # Throughput
            summary_data["Parameter"].append("Throughput")
            summary_data["Nilai"].append(report["throughput"]["kbps"])
            summary_data["Satuan"].append("kbps")
            summary_data["Standar"].append("ETSI TIPHON")
            
            # Jitter
            summary_data["Parameter"].append("Jitter")
            summary_data["Nilai"].append(report["jitter"]["average_ms"])
            summary_data["Satuan"].append("ms")
            summary_data["Standar"].append("RFC 3550")
            
            # PDR
            summary_data["Parameter"].append("Packet Delivery Ratio")
            summary_data["Nilai"].append(report["pdr"]["percentage"])
            summary_data["Satuan"].append("%")
            summary_data["Standar"].append("-")
            
            df = pd.DataFrame(summary_data)
            csv_file = f"qos_report_{timestamp}.csv"
            df.to_csv(csv_file, index=False)
            print(f"📁 QoS report exported to {csv_file}")
            
            # Export detailed packet log
            if self.packet_log:
                df_details = pd.DataFrame(self.packet_log)
                details_file = f"qos_packet_details_{timestamp}.csv"
                df_details.to_csv(details_file, index=False)
                print(f"📁 Packet details exported to {details_file}")
        
        elif format == 'json':
            json_file = f"qos_report_{timestamp}.json"
            with open(json_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"📁 QoS report exported to {json_file}")
    
    def plot_qos_results(self, report):
        """
        Membuat visualisasi hasil pengujian QoS
        """
        if not self.packet_log:
            print("No packet data available for plotting")
            return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('LoRa QoS Test Results', fontsize=16, fontweight='bold')
        
        # 1. Delay over time
        df = pd.DataFrame(self.packet_log)
        ax1 = axes[0, 0]
        ax1.plot(df['seq'], df['delay_ms'], 'b-o', markersize=4, linewidth=1)
        ax1.set_xlabel('Packet Sequence Number')
        ax1.set_ylabel('Delay (ms)')
        ax1.set_title(f'Packet Delay (Avg: {report["delay"]["average_ms"]} ms)')
        ax1.grid(True, alpha=0.3)
        
        # 2. Delay Distribution (Histogram)
        ax2 = axes[0, 1]
        ax2.hist(df['delay_ms'], bins=30, color='skyblue', edgecolor='black')
        ax2.set_xlabel('Delay (ms)')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Delay Distribution')
        ax2.axvline(report["delay"]["average_ms"], color='red', linestyle='--', 
                   label=f'Mean: {report["delay"]["average_ms"]} ms')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. Packet Size vs Delay
        ax3 = axes[1, 0]
        scatter = ax3.scatter(df['size_bytes'], df['delay_ms'], c=df['seq'], 
                             cmap='viridis', alpha=0.6)
        ax3.set_xlabel('Packet Size (bytes)')
        ax3.set_ylabel('Delay (ms)')
        ax3.set_title('Packet Size vs Delay Correlation')
        plt.colorbar(scatter, ax=ax3, label='Sequence Number')
        ax3.grid(True, alpha=0.3)
        
        # 4. QoS Metrics Summary
        ax4 = axes[1, 1]
        metrics = ['Delay (ms)', 'Packet Loss (%)', 'Jitter (ms)', 'PDR (%)']
        values = [
            report["delay"]["average_ms"],
            report["packet_loss"]["percentage"],
            report["jitter"]["average_ms"],
            report["pdr"]["percentage"]
        ]
        colors = ['blue', 'red', 'orange', 'green']
        bars = ax4.bar(metrics, values, color=colors)
        ax4.set_ylabel('Value')
        ax4.set_title('QoS Metrics Summary')
        
        # Add value labels on bars
        for bar, value in zip(bars, values):
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{value:.2f}', ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save figure
        plot_file = f"qos_plot_{timestamp}.png"
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"📊 QoS plot saved to {plot_file}")
        
        # Show plot
        plt.show()
    
    def print_qos_report(self, report):
        """
        Mencetak laporan QoS ke konsol dengan format yang rapi
        """
        if report is None:
            return
        
        print("\n" + "="*70)
        print("📡 QUALITY OF SERVICE (QoS) TEST REPORT")
        print("="*70)
        
        # Test Info
        print("\n📋 TEST INFORMATION")
        print("-"*50)
        print(f"  Test Name           : {report['test_info']['test_name']}")
        print(f"  Test Duration       : {report['test_info']['test_duration_seconds']} seconds")
        print(f"  Start Time          : {report['test_info']['start_time']}")
        print(f"  End Time            : {report['test_info']['end_time']}")
        print(f"  Total Packets Sent  : {report['test_info']['total_packets_sent']}")
        print(f"  Total Packets Recv  : {report['test_info']['total_packets_received']}")
        print(f"  Missing Packets     : {report['test_info']['missing_packets']}")
        
        # Delay
        print("\n⏱️ DELAY (RFC 2679)")
        print("-"*50)
        print(f"  Formula: Delay = Waktu Diterima - Waktu Dikirim")
        print(f"  Average Delay       : {report['delay']['average_ms']} ms")
        print(f"  Minimum Delay       : {report['delay']['minimum_ms']} ms")
        print(f"  Maximum Delay       : {report['delay']['maximum_ms']} ms")
        print(f"  Std Deviation       : {report['delay']['std_deviation_ms']} ms")
        
        # Packet Loss
        print("\n📦 PACKET LOSS (ETSI TIPHON)")
        print("-"*50)
        print(f"  Formula: Packet Loss(%) = (Paket Dikirim - Paket Diterima)/Paket Dikirim × 100%")
        print(f"  Packet Loss         : {report['packet_loss']['percentage']} %")
        
        # Throughput
        print("\n🚀 THROUGHPUT (ETSI TIPHON)")
        print("-"*50)
        print(f"  Formula: Throughput = Jumlah Data / Waktu Pengiriman")
        print(f"  Throughput          : {report['throughput']['kbps']} kbps")
        print(f"  Throughput          : {report['throughput']['bps']} bps")
        print(f"  Total Data Transfer : {report['throughput']['total_bytes']} bytes")
        
        # Jitter
        print("\n🔄 JITTER (RFC 3550)")
        print("-"*50)
        print(f"  Formula: Jitter = Σ|Delay_i - Delay_(i-1)| / (n-1)")
        print(f"  Average Jitter      : {report['jitter']['average_ms']} ms")
        
        # PDR
        print("\n📊 PACKET DELIVERY RATIO (PDR)")
        print("-"*50)
        print(f"  PDR                 : {report['pdr']['percentage']} %")
        
        # QoS Rating
        print("\n⭐ QOS RATING (ETSI TIPHON STANDARD)")
        print("-"*50)
        print(f"  Rating              : {report['qos_rating']['rating']}")
        print(f"  Score               : {report['qos_rating']['score']}/16")
        print(f"  Description         : {report['qos_rating']['description']}")
        
        print("\n" + "="*70)
        print("📌 INTERPRETASI STANDAR QoS")
        print("="*70)
        print("  • Delay < 150ms     : Excellent untuk real-time")
        print("  • Delay 150-300ms   : Good")
        print("  • Delay 300-450ms   : Fair")
        print("  • Delay > 450ms     : Poor")
        print("")
        print("  • Packet Loss < 1%  : Excellent")
        print("  • Packet Loss 1-3%  : Good")
        print("  • Packet Loss 3-5%  : Fair")
        print("  • Packet Loss > 5%  : Poor")
        print("")
        print("  • Jitter < 20ms     : Excellent")
        print("  • Jitter 20-50ms    : Good")
        print("  • Jitter 50-100ms   : Fair")
        print("  • Jitter > 100ms    : Poor")
        print("="*70)


# ===============================================================
# INTEGRASI DENGAN SISTEM UTAMA
# ===============================================================

def run_qos_test_integration(lora_receiver, duration_seconds=300):
    """
    Fungsi untuk menjalankan QoS test dari sistem utama
    
    Args:
        lora_receiver: Objek LoRa receiver (rfm9x)
        duration_seconds: Durasi pengujian dalam detik
    
    Returns:
        report: Laporan QoS
    """
    qos_tester = LoRaQoSTester(
        test_duration_seconds=duration_seconds,
        test_name=f"lora_qos_test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    
    report = qos_tester.run_qos_test(lora_receiver, duration_seconds)
    
    if report:
        # Print report
        qos_tester.print_qos_report(report)
        
        # Export report
        qos_tester.export_qos_report(report, format='csv')
        qos_tester.export_qos_report(report, format='json')
        
        # Plot results (optional, comment if no display)
        try:
            qos_tester.plot_qos_results(report)
        except Exception as e:
            print(f"⚠️ Plotting error (may need display): {e}")
        
        return report
    
    return None


# ===============================================================
# MENU INTERAKTIF UNTUK QoS TESTING
# ===============================================================

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
    print("5. Back to Main System")
    
    choice = input("\nPilih opsi (1-5): ").strip()
    
    durations = {
        '1': 60,
        '2': 300,
        '3': 900
    }
    
    if choice in durations:
        return durations[choice]
    elif choice == '4':
        try:
            minutes = int(input("Masukkan durasi (menit): "))
            return minutes * 60
        except:
            print("Invalid input, using default 5 minutes")
            return 300
    elif choice == '5':
        return None
    else:
        print("Invalid choice, using default 5 minutes")
        return 300


# ===============================================================
# CONTOH PENGGUNAAN
# ===============================================================
if __name__ == "__main__":
    """
    Contoh penggunaan QoS tester secara standalone
    (Tanpa LoRa hardware, untuk testing logic)
    """
    print("QoS Testing Module for LoRa Communication")
    print("Import this module and integrate with your LoRa receiver")
    
    # Example dengan simulated data
    class MockLoRaReceiver:
        def receive(self, timeout):
            import random
            time.sleep(random.uniform(0.01, 0.1))
            # Simulate packet
            return f'{{"t":30.5,"h":65.2,"p":1013,"d":1500,"lv":2,"sq":{random.randint(1,1000)},"ts":"2026-05-16 12:00:00"}}'.encode()
    
    # Run test with mock receiver (for demonstration)
    # mock_receiver = MockLoRaReceiver()
    # run_qos_test_integration(mock_receiver, duration_seconds=30)