import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def generate_qos_charts_from_json():
    json_file_path = "qos_log.json"
    
    # Validasi keberadaan file json hasil uji nyata
    if not os.path.exists(json_file_path):
        print(f" ⚠ File '{json_file_path}' tidak ditemukan. Jalankan program utama LoRa terlebih dahulu!")
        return
        
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)
            
        df = pd.DataFrame(data)
        if df.empty:
            print(" ⚠ Data pengujian di dalam file JSON masih kosong.")
            return
            
        print(f" 📊 Memproses {len(df)} baris data nyata dari JSON untuk plotting grafik...")
        
        # ===============================================================
        # EKSTRAKSI RENTANG TANGGAL DAN JAM SECARA OTOMATIS
        # ===============================================================
        # Pastikan kolom waktu tipenya datetime agar bisa diurutkan dengan benar
        # Urutkan berdasarkan waktu terlebih dahulu agar periode awal-akhir benar
        df['waktu'] = pd.to_datetime(df['waktu'])
        df = df.sort_values('waktu')  # <-- UBAH KE 'waktu' SEBELUM MENGAMBIL ILOC

        waktu_awal = df['waktu'].iloc[0].strftime('%d-%m-%Y %H:%M:%S')
        waktu_akhir = df['waktu'].iloc[-1].strftime('%d-%m-%Y %H:%M:%S')
        rentang_waktu = f"Periode Pengujian: {waktu_awal} s.d {waktu_akhir}"
        
        # Set up visualisasi matplotlib
        sns.set_theme(style="whitegrid")
        fig, axes = plt.subplots(2, 2, figsize=(14, 10)) # Tinggi dinaikkan sedikit agar muat teks tambahan
        
        # Menampilkan Judul Utama beserta Rentang Tanggal & Jam Pengujian
        judul_lengkap = f"GRAFIK ANALISIS QUALITY OF SERVICE (QoS) TRANSMISI LORA\n({rentang_waktu})"
        fig.suptitle(judul_lengkap, fontsize=13, fontweight='bold', y=0.96)
        
        # Plot 1: Delay & Jitter
        axes[0, 0].plot(df['seq_number'], df['delay_ms'], label='Delay (ms)', color='#1f77b4', linewidth=2)
        axes[0, 0].plot(df['seq_number'], df['jitter_ms'], label='Jitter (ms)', color='#ff7f0e', linestyle='--')
        axes[0, 0].set_title('Fluktuasi Jeda Waktu (Delay & Jitter)')
        axes[0, 0].set_xlabel('Sequence Number')
        axes[0, 0].set_ylabel('Milidetik (ms)')
        axes[0, 0].legend()
        
        # Plot 2: Throughput
        axes[0, 1].plot(df['seq_number'], df['throughput_bps'], color='#2ca02c', linewidth=2)
        axes[0, 1].set_title('Kecepatan Transfer Data Bersih (Throughput)')
        axes[0, 1].set_xlabel('Sequence Number')
        axes[0, 1].set_ylabel('Bits per Second (bps)')
        
        # Plot 3: Packet Loss
        axes[1, 0].plot(df['seq_number'], df['packet_loss_percent'], color='#d62728', linewidth=2)
        axes[1, 0].set_title('Persentase Kehilangan Data (Packet Loss %)')
        axes[1, 0].set_xlabel('Sequence Number')
        axes[1, 0].set_ylabel('Rasio Gagal (%)')
        
        # Plot 4: Korelasi RSSI vs Delay
        axes[1, 1].scatter(df['rssi'], df['delay_ms'], color='#9467bd', alpha=0.6)
        axes[1, 1].set_title('Analisis Korelasi Kekuatan Sinyal (RSSI) vs Delay')
        axes[1, 1].set_xlabel('RSSI (dBm)')
        axes[1, 1].set_ylabel('Delay (ms)')
        
        # Mengatur padding agar layout tidak tumpang tindih dengan judul bertingkat
        plt.tight_layout(rect=[0, 0.03, 1, 0.92])
        
        output_filename = "grafik_pengukuran_qos_json.png"
        plt.savefig(output_filename, dpi=300)
        print(f" ✅ File visualisasi '{output_filename}' sukses diexport dengan info rentang waktu pengujian.")
        
    except Exception as e:
        print(f" ❌ Terjadi kesalahan saat membaca atau melakukan komputasi grafik: {e}")

if __name__ == "__main__":
    generate_qos_charts_from_json()