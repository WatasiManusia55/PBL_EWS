import serial
import time

class WarningNode:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # tunggu ESP32 siap

    def send_status(self, status):
        self.ser.write(f"{status}\n".encode())
        print(f"[WARNING NODE] Kirim: {status}")