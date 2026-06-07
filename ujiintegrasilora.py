from lora_receiver import LoRaReceiver
import datetime
import re

lora = LoRaReceiver()

received_packets = set()

print("=== LoRa Integration Test ===")

while True:

    packet = lora.receive(timeout=5)

    if packet is None:
        continue

    try:
        data = packet.decode("utf-8")

        print(
            f"[{datetime.datetime.now()}] "
            f"{data}"
        )

        rssi = lora.get_last_rssi()

        print(f"RSSI = {rssi} dBm")

        match = re.search(r'ID:(\d+)', data)

        if match:

            packet_id = int(match.group(1))

            received_packets.add(packet_id)

            expected = max(received_packets)
            received = len(received_packets)

            loss = (
                (expected - received)
                / expected
            ) * 100

            print(
                f"Received={received} "
                f"Expected={expected} "
                f"Loss={loss:.2f}%"
            )

    except Exception as e:
        print("ERROR:", e)