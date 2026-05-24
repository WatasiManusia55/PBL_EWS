# PENGUJIAN INTGRASI .3
import time
import json
import re
import datetime
import digitalio
import board
import busio
import adafruit_rfm9x

# =====================================================
# KONFIGURASI LORA
# =====================================================
FREQ = 915.0

spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.D4)
reset = digitalio.DigitalInOut(board.D25)

rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, FREQ)

rfm9x.tx_power = 13
rfm9x.signal_bandwidth = 125000
rfm9x.coding_rate = 5
rfm9x.spreading_factor = 10
rfm9x.enable_crc = True

print("✅ LoRa Receiver Ready")
print("=" * 100)

# =====================================================
# PARSER DATA
# =====================================================
def parse_packet(raw):
    raw = raw.strip()

    if not raw.startswith("{"):
        raw = "{" + raw

    if not raw.endswith("}"):
        raw += "}"

    raw = re.sub(r'([a-zA-Z]+):', r'"\1":', raw)
    raw = raw.replace("'", '"')

    try:
        return json.loads(raw)
    except:
        return None

# =====================================================
# VARIABEL PENGUJIAN
# =====================================================
TOTAL_PACKET = 0
VALID_PACKET = 0
INVALID_PACKET = 0

received_sequence = []

start_time = time.time()

# =====================================================
# PROSES PENGUJIAN
# =====================================================
print("📡 MENUNGGU DATA LORA...")
print("=" * 100)

try:

    while TOTAL_PACKET < 10:

        packet = rfm9x.receive(timeout=5.0)

        if packet is not None:

            TOTAL_PACKET += 1

            raw_data = packet.decode("utf-8", errors="ignore")
            parsed = parse_packet(raw_data)

            rssi = rfm9x.last_rssi

            print(f"\n📩 PACKET #{TOTAL_PACKET}")
            print("-" * 100)
            print(f"Waktu         : {datetime.datetime.now()}")
            print(f"Raw Data      : {raw_data}")
            print(f"RSSI          : {rssi} dBm")

            if parsed:

                VALID_PACKET += 1

                seq = parsed.get("sq", None)

                if seq is not None:
                    received_sequence.append(seq)

                print("Status        : VALID")
                print(f"Parsed Data   : {parsed}")

            else:

                INVALID_PACKET += 1

                print("Status        : INVALID / CORRUPT")

        else:
            print("⌛ Tidak ada packet diterima")

    # =====================================================
    # ANALISIS DATA LOSS
    # =====================================================
    data_loss = 0

    if len(received_sequence) > 1:

        received_sequence.sort()

        expected = list(range(
            received_sequence[0],
            received_sequence[-1] + 1
        ))

        data_loss = len(set(expected) - set(received_sequence))

    # =====================================================
    # SUMMARY PENGUJIAN
    # =====================================================
    print("\n" + "=" * 100)
    print("📊 SUMMARY PENGUJIAN LORA")
    print("=" * 100)

    print(f"Total Packet Diterima    : {TOTAL_PACKET}")
    print(f"Packet Valid             : {VALID_PACKET}")
    print(f"Packet Invalid           : {INVALID_PACKET}")
    print(f"Data Loss                : {data_loss}")
    print(f"Sequence Diterima        : {received_sequence}")

    if TOTAL_PACKET > 0:
        success_rate = (VALID_PACKET / TOTAL_PACKET) * 100
    else:
        success_rate = 0

    print(f"Keberhasilan Penerimaan  : {success_rate:.2f}%")

    # =====================================================
    # KESIMPULAN
    # =====================================================
    print("\n📌 KESIMPULAN")

    if INVALID_PACKET == 0 and data_loss == 0:
        print("✅ Data LoRa diterima lengkap dan tidak mengalami kerusakan.")
        print("✅ Integrasi LoRa dengan Raspberry Pi berjalan dengan baik.")

    elif INVALID_PACKET > 0 or data_loss > 0:
        print("⚠️ Terdapat packet rusak atau data loss pada komunikasi LoRa.")
        print("⚠️ Integrasi masih berjalan tetapi perlu optimasi kualitas komunikasi.")

except KeyboardInterrupt:
    print("\n🛑 Pengujian dihentikan")