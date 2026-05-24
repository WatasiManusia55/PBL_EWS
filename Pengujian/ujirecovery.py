# PENGUJIAN RECOVERY .5
import subprocess
import time
from datetime import datetime

SERVICE_NAME = "ews.service"

def get_status():
    result = subprocess.run(
        ["systemctl", "is-active", SERVICE_NAME],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def get_pid():
    result = subprocess.run(
        ["systemctl", "show", SERVICE_NAME, "--property=MainPID"],
        capture_output=True,
        text=True
    )

    return result.stdout.strip().split("=")[1]

print("=== PENGUJIAN RECOVERY BACKEND ===")

pid = get_pid()

print(f"PID Backend : {pid}")

print("Membunuh backend...")
subprocess.run(["sudo", "kill", "-9", pid])

# Tunggu sampai service benar-benar down/restarting
print("Menunggu perubahan status service...")

while True:
    status = get_status()

    print(f"[{datetime.now()}] Status: {status}")

    if status != "active":
        break

    time.sleep(1)

print("\nService terdeteksi restart...")
start = time.time()

# Tunggu service kembali active
while True:
    status = get_status()

    print(f"[{datetime.now()}] Status: {status}")

    if status == "active":
        recovery_time = round(time.time() - start, 2)

        print("\n=== HASIL ===")
        print("Recovery berhasil")
        print(f"Recovery Time: {recovery_time} detik")
        break

    time.sleep(1)