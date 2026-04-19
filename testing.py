import board
import busio
import digitalio
import adafruit_rfm9x
import time

# Konfigurasi Pin sesuai data lo (BCM)
CS = digitalio.DigitalInOut(board.D4)    # Pin 7 (GPIO 4)
RESET = digitalio.DigitalInOut(board.D25) # Pin 22 (GPIO 25)

# Setup SPI
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

print("--- Memulai Test Komunikasi LoRa ---")

try:
    # Inisialisasi modul
    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 915.0)
    
    print("✅ Berhasil!")
    print(f"Modul Terdeteksi: RFM9x")
    
    # Cara baca versi chip di versi library terbaru
    # Register 0x42 adalah versi chip (default harusnya 0x12)
    version = rfm9x._read_u8(0x42) 
    print(f"Versi Chip (ID): {hex(version)}")
    
    print("Wiring lo udah bener dan modul dalam kondisi hidup.")

except RuntimeError as e:
    print("❌ Gagal!")
    print(f"Pesan Error: {e}")
    print("\nCoba cek hal berikut:")
    print("1. Pastikan kabel Merah (3.3V) dan Hitam (GND) nggak kendor.")
    print("2. Cek kabel Biru (CS) di GPIO 4, pastikan beneran masuk ke Pin 7.")
    print("3. Pastikan SPI sudah di-enable di raspi-config.")
except Exception as ex:
    print(f"❌ Error Tak Terduga: {ex}")

finally:
    print("--- Test Selesai ---")