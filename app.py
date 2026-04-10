#!/usr/bin/env python3
"""
============================================================
 LoRa Receiver — Raspberry Pi 4 + RFM95W
 FIX WIRING: Pin 7 (GPIO 4) as NSS
============================================================
 Wiring RFM95W → Raspberry Pi 4:
   RFM95W    Raspi GPIO (BCM)    Pin Fisik
   ──────    ─────────────────   ─────────
   3.3V    → Pin 1  (3.3V)       = Merah
   GND     → Pin 6  (GND)        = Coklat
   MOSI    → Pin 19 (GPIO10)     = Ungu
   MISO    → Pin 21 (GPIO9)      = Kuning
   SCK     → Pin 23 (GPIO11)     = Hijau Tua
   NSS     → Pin 7  (GPIO4)      ← CS (BIRU) - PIN PINDAH!
   RST     → Pin 22 (GPIO25)     = Hijau Muda
   DIO0    → Pin 18 (GPIO24)     = Oranye
   DIO1    → Pin 16 (GPIO23)     = Putih/Hijau
============================================================
"""

import time
import json
import csv
import os
import signal
import traceback
import board
import busio
import digitalio
import adafruit_rfm9x

# ============================================================
#  KONFIGURASI
# ============================================================
LORA_FREQ_MHZ   = 915.0
LORA_SF         = 10
LORA_BW         = 125000
LORA_CR         = 5
LORA_SYNC_WORD  = 0x12
LORA_PREAMBLE   = 8

CSV_FILE        = "lora_data.csv"
TIMEOUT_SEC     = 5.0
SEQ_GAP_ALERT   = 3

# Header CSV sesuai data sensor
CSV_HEADER = [
    "timestamp", "seq", "temp_c", "humidity_pct", "pressure_hpa",
    "distance_mm", "flow_l", "rain_total_mm", "rain_rate_mmph",
    "float_level", "alert", "rssi_dbm", "snr_db"
]

# ============================================================
#  SETUP GPIO & SPI
# ============================================================
def init_lora():
    print("[LoRa] Inisialisasi RFM95W...")
    
    # Inisialisasi SPI Hardware
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

    # Definisi Pin sesuai kesepakatan wiring aman
    cs   = digitalio.DigitalInOut(board.D4)   # Pin 7 (NSS) - Anti Busy
    rst  = digitalio.DigitalInOut(board.D25)  # Pin 22 (RST)
    
    # Inisialisasi library rfm9x
    # Baudrate diturunkan ke 1MHz agar kabel jumper panjang tidak error
    try:
        rfm = adafruit_rfm9x.RFM9x(spi, cs, rst, LORA_FREQ_MHZ, baudrate=1000000)
    except Exception as e:
        print(f"❌ [ERR] Hardware RFM95W tidak ditemukan!")
        print(f"Detail: {e}")
        exit(1)

    # Parameter Radio
    rfm.spreading_factor   = LORA_SF
    rfm.signal_bandwidth   = LORA_BW
    rfm.coding_rate        = LORA_CR
    rfm.preamble_length    = LORA_PREAMBLE
    rfm.enable_crc         = True
    
    # Sync word untuk private network (Register 0x39)
    rfm._device.write_u8(0x39, LORA_SYNC_WORD)

    print(f"✅ LoRa OK — {LORA_FREQ_MHZ} MHz | SF{LORA_SF} | CS: Pin 7 (GPIO 4)")
    return rfm

# ============================================================
#  FUNGSI UTILTAS (CSV & PRINT)
# ============================================================
def init_csv():
    write_header = not os.path.exists(CSV_FILE)
    f = open(CSV_FILE, "a", newline="")
    writer = csv.writer(f)
    if write_header:
        writer.writerow(CSV_HEADER)
        f.flush()
    return f, writer

def pretty_print(data, rssi, snr, ts, seq_prev):
    seq = data.get("sq", -1)
    gap = (seq - seq_prev - 1) if seq_prev >= 0 and seq > seq_prev else 0

    print(f"\n[{ts}] 📥 PAKET DITERIMA | RSSI: {rssi} dBm | SNR: {snr} dB")
    print(f"   Seq: {seq} | Status: {'⚠️ LOSS ' + str(gap) if gap > 0 else 'OK'}")
    print(f"   🌡️  {data.get('t', 0):>4.1f}°C | 💧 {data.get('h', 0):>4.1f}% | 📏 {data.get('d', 0):>4}mm")
    
    if data.get("al"):
        print("   🚨 ALERT: LEVEL AIR TINGGI!")
    print("-" * 50)

# ============================================================
#  MAIN PROGRAM
# ============================================================
running = True
def signal_handler(sig, frame):
    global running
    print("\n[SYSTEM] Menutup program...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

def main():
    rfm = init_lora()
    csv_f, csv_writer = init_csv()
    seq_prev = -1

    print("[SYSTEM] Menunggu data sensor dari ESP32...\n")

    while running:
        try:
            # Terima data (timeout 5 detik)
            packet = rfm.receive(timeout=TIMEOUT_SEC)

            if packet is not None:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Decode bytes ke String lalu JSON
                try:
                    raw_str = str(packet, "utf-8", "ignore")
                    data = json.loads(raw_str)
                except Exception as e:
                    print(f"⚠️ [ERR] Gagal decode data: {e}")
                    continue

                # Tampilkan di layar
                pretty_print(data, rfm.last_rssi, rfm.last_snr, ts, seq_prev)
                seq_prev = data.get("sq", -1)

                # Simpan ke CSV
                row = [
                    ts, data.get("sq"), data.get("t"), data.get("h"), data.get("p"),
                    data.get("d"), data.get("f"), data.get("rt"), data.get("rr"),
                    data.get("lv"), data.get("al"), rfm.last_rssi, rfm.last_snr
                ]
                csv_writer.writerow(row)
                csv_f.flush()

        except Exception as e:
            print(f"⚠️ [LOOP ERR] {e}")
            time.sleep(1)

    csv_f.close()
    print("[SYSTEM] Selesai.")

if __name__ == "__main__":
    main()