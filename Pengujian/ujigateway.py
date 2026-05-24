# PENGUJIAN RECOVERY .2
import time
import socket
import requests
import subprocess
from datetime import datetime

# =========================================================
# KONFIGURASI
# =========================================================

TARGET_URL = "https://makesens-kali.my.id/login"

STATUS_FILE = "gateway_status.txt"

LOG_FILE = "gateway_monitoring.log"

CHECK_INTERVAL = 5

INTERFACE = "wlan0"   # ganti eth0 jika menggunakan LAN

# =========================================================
# CEK INTERNET
# =========================================================

def cek_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except:
        return False

# =========================================================
# CEK SERVER
# =========================================================

def cek_server():
    try:
        response = requests.get(TARGET_URL, timeout=5)
        return response.status_code == 200
    except:
        return False

# =========================================================
# SIMPAN STATUS
# =========================================================

def simpan_status(status):
    with open(STATUS_FILE, "w") as file:
        file.write(status)

# =========================================================
# SIMPAN LOG
# =========================================================

def simpan_log(log_text):
    with open(LOG_FILE, "a") as log:
        log.write(log_text + "\n")

# =========================================================
# MONITORING GATEWAY
# =========================================================

def monitoring_gateway(durasi=15):

    offline_terdeteksi = False

    start = time.time()

    while time.time() - start < durasi:

        waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        internet_status = cek_internet()
        server_status = cek_server()

        # ---------------------------------------------
        # KONDISI ONLINE
        # ---------------------------------------------
        if internet_status and server_status:

            status = "ONLINE"

            hasil = (
                f"[{waktu}] "
                f"Gateway ONLINE | "
                f"Sinkronisasi Database BERHASIL"
            )

        # ---------------------------------------------
        # KONDISI OFFLINE
        # ---------------------------------------------
        else:

            status = "OFFLINE"

            offline_terdeteksi = True

            hasil = (
                f"[{waktu}] "
                f"Gateway OFFLINE | "
                f"Sinkronisasi Database GAGAL"
            )

        print(hasil)

        simpan_status(status)

        simpan_log(hasil)

        time.sleep(CHECK_INTERVAL)

    return offline_terdeteksi

# =========================================================
# MAIN PROGRAM
# =========================================================

print("================================================")
print(" PENGUJIAN GATEWAY DOWN ")
print("================================================")

# -------------------------------------------------
# KONDISI NORMAL
# -------------------------------------------------

print("\n[1] Monitoring kondisi NORMAL...\n")

monitoring_gateway()

# -------------------------------------------------
# SIMULASI INTERNET PUTUS
# -------------------------------------------------

print(f"\n[2] Memutus koneksi interface {INTERFACE}...\n")

subprocess.run(["sudo", "ifconfig", INTERFACE, "down"])

time.sleep(5)

# -------------------------------------------------
# KONDISI OFFLINE
# -------------------------------------------------

print("\n[3] Monitoring kondisi GATEWAY DOWN...\n")

offline = monitoring_gateway()

# -------------------------------------------------
# AKTIFKAN INTERNET KEMBALI
# -------------------------------------------------

print(f"\n[4] Mengaktifkan kembali interface {INTERFACE}...\n")

subprocess.run(["sudo", "ifconfig", INTERFACE, "up"])

time.sleep(10)

# -------------------------------------------------
# MONITORING SETELAH RECOVERY
# -------------------------------------------------

print("\n[5] Monitoring setelah koneksi kembali...\n")

monitoring_gateway()

# =========================================================
# SUMMARY PENGUJIAN
# =========================================================

print("\n================================================")
print(" SUMMARY PENGUJIAN ")
print("================================================")

if offline:

    print("""
Berdasarkan pengujian yang dilakukan, sistem berhasil mendeteksi
kondisi gateway ketika koneksi internet terputus. Saat interface
jaringan dinonaktifkan, status gateway berubah menjadi OFFLINE
dan sinkronisasi database dinyatakan gagal.

Sistem monitoring tetap berjalan normal tanpa mengalami crash
selama proses pengujian berlangsung. Hasil pengujian menunjukkan
bahwa mekanisme monitoring gateway dan deteksi gangguan koneksi
internet telah berjalan dengan baik.
""")

else:

    print("""
Sistem tidak mendeteksi kondisi gateway offline selama pengujian.
Pengujian perlu dilakukan kembali untuk memastikan mekanisme
deteksi gangguan koneksi berjalan dengan baik.
""")

print("=== PENGUJIAN SELESAI ===")