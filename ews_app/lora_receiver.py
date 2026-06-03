# lora_receiver.py
import digitalio
import board
import busio
import adafruit_rfm9x
from config import FREQ

class LoRaReceiver:
    def __init__(self):
        self.spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        self.cs = digitalio.DigitalInOut(board.D4)
        self.reset = digitalio.DigitalInOut(board.D25)
        self.rfm9x = adafruit_rfm9x.RFM9x(self.spi, self.cs, self.reset, FREQ)
        self._configure()
        print("✅ LoRa Aktif")
        
    def _configure(self):
        """Configure LoRa radio"""
        self.rfm9x.tx_power = 15
        self.rfm9x.signal_bandwidth = 125000
        self.rfm9x.coding_rate = 6
        self.rfm9x.spreading_factor = 10
        self.rfm9x.enable_crc = True
        self.rfm9x.sync_word = 0x12
        
    def receive(self, timeout=1.0):
        """Receive packet from LoRa"""
        return self.rfm9x.receive(timeout=timeout)
        
    def get_last_rssi(self):
        """Get RSSI of last received packet"""
        return self.rfm9x.last_rssi
        
    def get_live_rssi(self):
        """Get live RSSI from LoRa register"""
        try:
            raw = self.rfm9x._read_u8(0x1B)
            return raw - 157
        except:
            return -999