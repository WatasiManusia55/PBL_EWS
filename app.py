#!/usr/bin/env python3
# ===============================================================
# RASPBERRY PI RECEIVER FIXED
# + SAFE JSON PARSE
# + FILTER CORRUPT PACKET
# + POSTGRESQL STABLE INSERT
# ===============================================================

import time
import json
import datetime
import digitalio
import board
import busio
import adafruit_rfm9x
import psycopg2
import csv
import os

# ===============================================================
# DATABASE
# ===============================================================
conn = psycopg2.connect(
    host="localhost",
    database="ews_banjir",
    user="pi",
    password="ews"
)

cur = conn.cursor()
print("✅ PostgreSQL Connected")

# ===============================================================
# CONFIG
# ===============================================================
FREQ = 915.0
TOTAL_PACKET = 0
LAST_WAIT_PRINT = 0

# ===============================================================
# INIT LORA
# ===============================================================
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.D4)
reset = digitalio.DigitalInOut(board.D25)

rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, FREQ)

rfm9x.tx_power = 13
rfm9x.signal_bandwidth = 125000
rfm9x.coding_rate = 5
rfm9x.spreading_factor = 10
rfm9x.enable_crc = True

print("✅ LoRa Aktif")
print("-" * 70)

# ===============================================================
# CSV SETUP
# ===============================================================

CSV_FILE = "sensor_data.csv"

CSV_HEADER = [
    "timestamp", "suhu", "kelembapan", "tekanan",
    "jarak_air", "flow",
    "rain_total", "rain_rate",
    "float_level", "alert",
    "seq", "rssi"
]

# buat file kalau belum ada
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)

print("📁 CSV Ready:", CSV_FILE)
# ===============================================================
# HELPER: CLEAN PACKET
# ===============================================================
def clean_packet(raw):
    """Fix packet ESP32 yang sering rusak"""
    raw = raw.strip()

    if not raw:
        return None

    # kalau tidak ada { di awal → paksa tambah
    if not raw.startswith("{"):
        raw = "{" + raw

    # kalau tidak ada } → tambah
    if not raw.endswith("}"):
        raw = raw + "}"

    # fix kasus ':' di awal data ESP32 kamu
    if raw.startswith("{:"):
        raw = raw.replace("{:", "{\"t\":", 1)

    return raw


# ===============================================================
# RSSI NOISE
# ===============================================================
def get_live_rssi():
    try:
        raw = rfm9x._read_u8(0x1B)
        return raw - 157
    except:
        return -999


def noise_label(v):
    if v <= -115:
        return "🟢 Bersih"
    elif v <= -105:
        return "🟡 Normal"
    elif v <= -95:
        return "🟠 Sedikit Noise"
    else:
        return "🔴 Bising"


# ===============================================================
# PRINT
# ===============================================================
def tampilkan_data(data, rssi):
    global TOTAL_PACKET
    TOTAL_PACKET += 1

    print("\n" + "═" * 70)
    print(f"📩 DATA #{TOTAL_PACKET}")
    print("🕒 Waktu :", datetime.datetime.now().strftime("%H:%M:%S"))
    print("📶 RSSI  :", rssi)
    print("🌡️ Suhu  :", data.get("t"))
    print("💧 Hum   :", data.get("h"))
    print("🌊 Level :", data.get("d"))
    print("═" * 70)


# ===============================================================
# DB INSERT
# ===============================================================
def simpan_csv(data, rssi):
    try:
        with open(CSV_FILE, "a", newline="") as f:
            writer = csv.writer(f)

            writer.writerow([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                data.get("t"),
                data.get("h"),
                data.get("p"),
                data.get("d"),
                data.get("f"),
                data.get("rt"),
                data.get("rr"),
                data.get("lv"),
                data.get("al"),
                data.get("sq"),
                rssi
            ])

        print("💾 CSV OK")

    except Exception as e:
        print("❌ CSV ERROR:", e)


# ===============================================================
# LOOP
# ===============================================================
print("📡 Receiver Ready")
print("-" * 70)

while True:
    try:
        packet = rfm9x.receive(timeout=1.0)

        if packet is not None:

            raw_str = packet.decode("utf-8", errors="ignore").strip()

            # ==============================
            # CLEAN PACKET (IMPORTANT)
            # ==============================
            raw_str = clean_packet(raw_str)

            # FILTER RUSAK
            if raw_str is None or not raw_str.startswith("{") or "}" not in raw_str:
                print("\n⚠️ Packet rusak dilewati:")
                print(raw_str)
                print("📶 RSSI:", rfm9x.last_rssi)
                continue

            # PARSE JSON
            try:
                data = json.loads(raw_str)

                simpan_csv(data, rfm9x.last_rssi)
                tampilkan_data(data, rfm9x.last_rssi)

            except json.JSONDecodeError:
                print("\n❌ JSON ERROR:")
                print(raw_str)
                print("📶 RSSI:", rfm9x.last_rssi)

        else:
            now = time.time()

            if now - LAST_WAIT_PRINT >= 2:
                noise = get_live_rssi()
                print(
                    f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                    f"⌛ Waiting... | Noise: {noise} dBm | {noise_label(noise)}"
                )
                LAST_WAIT_PRINT = now

        time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n🛑 STOP")
        break

    except Exception as e:
        print("❌ ERROR:", e)
        time.sleep(1)