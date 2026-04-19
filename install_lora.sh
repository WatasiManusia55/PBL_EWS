#!/bin/bash

echo "=== UPDATE SYSTEM ==="
sudo apt update && sudo apt upgrade -y

echo "=== INSTALL PYTHON & PIP ==="
sudo apt install -y python3 python3-pip python3-venv

echo "=== ENABLE SPI ==="
sudo raspi-config nonint do_spi 0

echo "=== INSTALL DEPENDENCY SYSTEM ==="
sudo apt install -y python3-dev libffi-dev libssl-dev

echo "=== INSTALL LIBRARY PYTHON ==="
pip3 install --upgrade pip

pip3 install \
adafruit-blinka \
adafruit-circuitpython-rfm9x \
RPi.GPIO \
paho-mqtt

echo "=== DONE ==="
echo "Silakan reboot: sudo reboot"