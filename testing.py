import time
import busio
import digitalio
import board
import json
import adafruit_rfm9x

# ==========================================
# 1. KONFIGURASI PIN & SPI
# ==========================================
CS_PIN    = board.D22 # Pin 15 Fisik
RESET_PIN = board.D25 # Pin 22 Fisik

# Setup SPI (MISO=P21, MOSI=P19, SCK=P23)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs = digitalio.DigitalInOut(CS_PIN)
reset = digitalio.DigitalInOut(RESET_PIN)

def inisialisasi_lora():
    """Melakukan reset hardware dan konfigurasi register RFM95"""
    print("\n" + "="*40)
    print("STEP 1: Melakukan Hard Reset Hardware...")
    reset.direction = digitalio.Direction.OUTPUT
    reset.value = False
    time.sleep(0.5)
    reset.value = True
    time.sleep(0.5)

    try:
        # Gunakan baudrate rendah (50kHz) untuk toleransi kabel jumper
        # Sesuaikan frekuensi ke 915.0 MHz (Sesuai ESP32 kamu)
        rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, 915.0, baudrate=50000)
        
        # SINKRONISASI DENGAN LIBRARY ESP32 (Sandeep Mistry)
        rfm9x.spreading_factor = 10     # LORA_SF 10
        rfm9x.signal_bandwidth = 125000 # LORA_BW 125 kHz
        rfm9x.coding_rate = 5           # LORA_CR 4/5 (Nilai 5 = 4/5)
        rfm9x.sync_word = 0x12          # LORA_SYNC_WORD 0x12 (Private)
        rfm9x.enable_crc = True
        rfm9x.preamble_length = 8
        
        # Test baca register pertama
        test_rssi = rfm9x.last_rssi
        print(f"STEP 2: Koneksi SPI Berhasil!")
        print(f"STEP 3: Status Awal - Noise: {test_rssi} dBm")
        print("="*40)
        return rfm9x

    except Exception as e:
        print(f"[!] GAGAL INIT: {e}")
        return None

# ==========================================
# 2. LOOP UTAMA (MONITORING & RECEIVER)
# ==========================================
radio = inisialisasi_lora()

if radio:
    print("\n>>> Gateway Aktif. Menunggu Paket dari ESP32...")
    print(">>> Jika Noise 0.0 atau -164, goyangkan kabel MISO/GND.\n")
    
    while True:
        try:
            # Polling paket tanpa header (Raw Mode)
            # Timeout 2 detik agar status noise terus terupdate
            packet = radio.receive(with_header=False, timeout=2.0)
            
            # Ambil status Noise saat ini
            current_rssi = radio.last_rssi
            
            if packet is None:
                # Logika deteksi error kabel lewat pembacaan RSSI
                if current_rssi == 0.0 or current_rssi < -140:
                    status_msg = f"KABEL ERROR ({current_rssi} dBm)"
                else:
                    status_msg = f"Standby | Noise: {current_rssi} dBm"
                
                print(f"[{time.strftime('%H:%M:%S')}] {status_msg}      ", end='\r')
            
            else:
                # JIKA DATA MASUK
                print("\n" + "*"*50)
                print(f"[{time.strftime('%H:%M:%S')}] PAKET DITERIMA!")
                print(f"Kekuatan Sinyal (RSSI): {current_rssi} dBm")
                print(f"Kualitas Sinyal (SNR): {radio.last_snr}")
                
                try:
                    # Bersihkan karakter null padding
                    raw_payload = bytes(packet).strip(b'\x00')
                    decoded_data = raw_payload.decode('utf-8')
                    
                    print(f"Payload Mentah: {decoded_data}")
                    
                    # Parsing JSON
                    data = json.loads(decoded_data)
                    
                    # Mapping Data Sensor ESP32
                    print(f"--- DATA SENSOR ---")
                    print(f"  Seq No     : {data.get('sq')}")
                    print(f"  Suhu       : {data.get('t')} C")
                    print(f"  Kelembaban : {data.get('h')} %")
                    print(f"  Jarak (A01): {data.get('d')} mm")
                    print(f"  Flow Air   : {data.get('f')} Liter")
                    print(f"  Curah Hujan: {data.get('rt')} mm")
                    
                    # Logika Alert
                    if data.get('al') == 1:
                        print("  [!!!] STATUS: ALERT (Kenalkan Air Cepat!)")
                    else:
                        status_lv = "TINGGI" if data.get('lv') == 1 else "NORMAL"
                        print(f"  [i] Status Level Air: {status_lv}")
                        
                except Exception as e:
                    print(f"  [!] Gagal memproses data: {e}")
                    print(f"  [!] Data Mentah: {packet}")
                
                print("*"*50 + "\n")

        except KeyboardInterrupt:
            print("\nProgram dihentikan oleh pengguna.")
            break
        except Exception as e:
            # Jika ada error SPI yang fatal, otomatis restart radio
            print(f"\n[!] Error Terdeteksi: {e}")
            print("Mencoba Inisialisasi Ulang dalam 3 detik...")
            time.sleep(3)
            radio = inisialisasi_lora()
            if not radio:
                print("Gagal Reconnect. Cek kabel fisik!")
                break
else:
    print("\n[GAGAL] Hardware tidak merespon. Cek Kabel 3.3V dan GND!")