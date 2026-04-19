import os
import time
import subprocess
import sys
from datetime import datetime

BASE = os.path.expanduser('~/Documents/Backend/PBL_EWS')
WEB = os.path.expanduser('~/Documents/Backend/PBL_EWS/ews-banjir')

PY = sys.executable
LOGFILE = os.path.join(BASE, 'receiver.log')

MENU = '''
╔══════════════════════════════════════════════════════╗
║            🚀 LoRa Control Center FINAL             ║
╠══════════════════════════════════════════════════════╣
║ 1. ▶ Start LoRa Receiver                           ║
║ 2. 🌐 Start Laravel Web                            ║
║ 3. 🗄️ Start PostgreSQL                             ║
║ 4. 🎥 Start MediaMTX                               ║
║ 5. 🚀 Start Semua Service                          ║
║ 6. 📊 Monitoring Dashboard                         ║
║ 7. 📤 Push GitHub                                  ║
║ 8. 📜 Lihat Log Terakhir                           ║
║ 9. 🧹 Bersihkan Layar                              ║
║10. ❌ Keluar                                       ║
╚══════════════════════════════════════════════════════╝
'''

def clear():
    os.system('clear')

def header():
    print(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 {BASE}\n")

def run(cmd):
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        print("\n⛔ Dihentikan → balik ke menu")

def safe_run(title, cmd):
    try:
        print(f"\n▶ {title} (Ctrl+C untuk kembali ke menu)\n")
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        print("\n⛔ Dihentikan, kembali ke menu...")
        time.sleep(1)

while True:
    try:
        clear()
        header()
        print(MENU)

        pilih = input("Pilih menu: ").strip()

        # 1. LoRa Receiver
        if pilih == '1':
            try:
                print("\n▶ LoRa Receiver jalan... (CTRL+C = kembali ke menu)\n")
                subprocess.run(f"cd {BASE} && {PY} app.py", shell=True)
            except KeyboardInterrupt:
                print("\n⛔ Receiver stop → kembali ke menu")
                time.sleep(1)

        elif pilih == '2':
            try:
                print("\n▶ Laravel Web STARTING (background)...\n")
                subprocess.Popen(
                    f"cd {WEB} && php artisan serve --host=0.0.0.0 --port=8080",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                print("✅ Laravel jalan di background (port 8080)")
                print("📶 Cek dengan: http://0.0.0.0:8080")
                input("\nEnter...")

            except Exception as e:
                print(f"❌ Error Laravel: {e}")
                input("\nEnter...")

        # 3. PostgreSQL
        elif pilih == '3':
            run("sudo systemctl start postgresql")
            run("systemctl status postgresql --no-pager")
            input("\nEnter...")

        # 4. MediaMTX
        elif pilih == '4':
            run("sudo systemctl start mediamtx")
            run("systemctl status mediamtx --no-pager")
            input("\nEnter...")

        # 5. Start semua (background)
        elif pilih == '5':
            print("\n🚀 Starting all services...\n")

            run("sudo systemctl start postgresql")
            run("sudo systemctl start mediamtx")

            run(f"nohup {PY} {BASE}/penerima.py > {BASE}/receiver.log 2>&1 &")
            run(f"cd {WEB} && nohup php artisan serve --host=0.0.0.0 --port=8000 > web.log 2>&1 &")

            print("✅ Semua service berjalan di background")
            input("\nEnter...")

        # 6. Monitoring
        elif pilih == '6':
            run("systemctl status postgresql --no-pager")
            run("systemctl status mediamtx --no-pager")
            input("\nEnter...")

        # 7. Git Push
        elif pilih == '7':
            run("bash /home/pi/Documents/Backend/PBL_EWS/push_github.sh")
            input("\nEnter...")

        # 8. Log
        elif pilih == '8':
            run(f"tail -n 50 {LOGFILE}")
            input("\nEnter...")

        # 9. Clear
        elif pilih == '9':
            clear()

        # 10. Exit
        elif pilih == '10':
            print("\n👋 Keluar...")
            break

        else:
            input("Pilihan tidak valid. Enter...")

    except KeyboardInterrupt:
        print("\n⛔ CTRL+C ditekan → kembali ke menu...")
        time.sleep(1)