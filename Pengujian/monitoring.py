import time
import os
import platform
import subprocess
import re
import psutil
import json
from datetime import datetime

JSON_FILE = "monitoring_log.json"

def get_cpu_usage():
    """Mengambil penggunaan CPU (%)"""
    return psutil.cpu_percent(interval=1)

def get_memory_usage():
    """Mengambil penggunaan RAM (%)"""
    return psutil.virtual_memory().percent

def get_rssi():
    """Mengambil RSSI Wi-Fi berdasarkan OS"""
    current_os = platform.system()
    rssi_value = None

    try:
        if current_os == "Windows":

            process = subprocess.Popen(
                ["netsh", "wlan", "show", "interfaces"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, _ = process.communicate()

            match = re.search(r"Signal\s*:\s*(\d+)%", stdout)

            if match:
                signal_percent = int(match.group(1))
                rssi_value = round((signal_percent / 2) - 100)
            else:
                rssi_value = None

        elif current_os == "Linux":

            process = subprocess.Popen(
                ["iwconfig"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, _ = process.communicate()

            match = re.search(r"Signal level=(-\d+|\d+)\s+dBm", stdout)

            if match:
                rssi_value = int(match.group(1))

            else:
                if os.path.exists("/proc/net/wireless"):

                    with open("/proc/net/wireless", "r") as f:
                        lines = f.readlines()

                        if len(lines) > 2:
                            data = lines[2].split()
                            rssi_value = int(float(data[3]))

        else:
            rssi_value = None

    except Exception as e:
        print(f"Error RSSI: {e}")
        rssi_value = None

    return rssi_value


def save_to_json(data):
    """Simpan data ke JSON"""

    all_data = []

    # Kalau file sudah ada, baca dulu
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as file:
                all_data = json.load(file)
        except:
            all_data = []

    # Tambah data baru
    all_data.append(data)

    # Simpan ulang
    with open(JSON_FILE, "w") as file:
        json.dump(all_data, file, indent=4)


if __name__ == "__main__":

    print("=" * 55)
    print(" SISTEM MONITORING PARAMETER")
    print(" CPU | MEMORY | RSSI ")
    print("=" * 55)

    try:
        while True:

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cpu = get_cpu_usage()
            memory = get_memory_usage()
            rssi = get_rssi()

            monitoring_data = {
                "timestamp": timestamp,
                "cpu_usage_percent": cpu,
                "memory_usage_percent": memory,
                "rssi_dbm": rssi
            }

            # Print ke terminal
            print(f"\n[{timestamp}]")
            print(f"CPU Usage    : {cpu}%")
            print(f"Memory Usage : {memory}%")
            print(f"RSSI Signal  : {rssi} dBm")

            # Simpan ke JSON
            save_to_json(monitoring_data)

            print("Status       : Data berhasil disimpan ke JSON")

            # Interval monitoring
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nMonitoring dihentikan.")