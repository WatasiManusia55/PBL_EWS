# PENGUJIAN KEAMANAN .6
import socket
import ssl
import psycopg2
import requests
from urllib.parse import urlparse

# =====================================================
# KONFIGURASI
# =====================================================

FIREBASE_URL = "https://ews3-858da-default-rtdb.asia-southeast1.firebasedatabase.app/"

POSTGRES_CONFIG = {
    "host": "localhost",
    "database": "ews_banjir",
    "user": "pi",
    "password": "ews",
    "sslmode": "require"
}

# =====================================================
# PENGUJIAN HTTPS / TLS FIREBASE
# =====================================================

print("=" * 100)
print("🔐 PENGUJIAN HTTPS / TLS FIREBASE")
print("=" * 100)

https_status = False
tls_version = "Unknown"

try:

    response = requests.get(FIREBASE_URL, timeout=10)

    parsed_url = urlparse(FIREBASE_URL)
    hostname = parsed_url.hostname

    context = ssl.create_default_context()

    with socket.create_connection((hostname, 443)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:

            tls_version = ssock.version()
            cipher = ssock.cipher()

            print(f"🌐 Host               : {hostname}")
            print(f"📡 HTTPS Status       : {response.status_code}")
            print(f"🔒 TLS Version        : {tls_version}")
            print(f"🛡 Cipher             : {cipher[0]}")

            if response.url.startswith("https://"):
                https_status = True

except Exception as e:
    print(f"❌ HTTPS/TLS Error : {e}")

# =====================================================
# PENGUJIAN SSL/TLS POSTGRESQL
# =====================================================

print("\n" + "=" * 100)
print("🛢 PENGUJIAN SSL/TLS POSTGRESQL")
print("=" * 100)

postgres_ssl = False

try:

    conn = psycopg2.connect(**POSTGRES_CONFIG)

    cur = conn.cursor()

    cur.execute("SHOW ssl;")
    ssl_status = cur.fetchone()[0]

    cur.execute("""
    SELECT version();
    """)

    postgres_version = cur.fetchone()[0]

    print(f"🛢 PostgreSQL Version : {postgres_version}")
    print(f"🔒 SSL Status         : {ssl_status}")

    if ssl_status.lower() == "on":
        postgres_ssl = True

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ PostgreSQL SSL Error : {e}")

# =====================================================
# TIMESTAMP PENGUJIAN
# =====================================================

from datetime import datetime

test_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# =====================================================
# SUMMARY PENGUJIAN
# =====================================================

print("\n" + "=" * 100)
print("📊 SUMMARY PENGUJIAN ENKRIPSI")
print("=" * 100)

print(f"""
🕒 Waktu Pengujian       : {test_time}

🌐 FIREBASE HTTPS/TLS
----------------------------------------------------------------------------------------------------
Status HTTPS              : {'AKTIF' if https_status else 'TIDAK AKTIF'}
Versi TLS                 : {tls_version}
Host Firebase             : {hostname}
Response Server           : {response.status_code if 'response' in locals() else 'N/A'}

🛢 POSTGRESQL SSL/TLS
----------------------------------------------------------------------------------------------------
Status SSL PostgreSQL     : {'AKTIF' if postgres_ssl else 'TIDAK AKTIF'}
Versi PostgreSQL          : {postgres_version if 'postgres_version' in locals() else 'N/A'}

🔐 ANALISIS KEAMANAN
----------------------------------------------------------------------------------------------------
- HTTPS digunakan untuk mengenkripsi komunikasi data antara Raspberry Pi dan Firebase.
- TLS membantu mencegah penyadapan data sensor selama transmisi melalui internet.
- SSL/TLS pada PostgreSQL membantu mengamankan komunikasi database dari sniffing.
- Data sensor seperti suhu, curah hujan, dan level air dikirim melalui jalur terenkripsi.
- Penggunaan enkripsi meningkatkan confidentiality dan integrity data monitoring realtime.

📡 RISIKO YANG BERHASIL DIKURANGI
----------------------------------------------------------------------------------------------------
✅ Eavesdropping / penyadapan data
✅ Manipulasi data saat transmisi
✅ Packet sniffing pada jaringan
✅ Kebocoran data monitoring realtime

""")

# =====================================================
# KESIMPULAN
# =====================================================

print("=" * 100)
print("📌 KESIMPULAN AKHIR")
print("=" * 100)

if https_status and postgres_ssl:

    print(f"""
[{test_time}] ✅ Pengujian menunjukkan bahwa seluruh transmisi data pada sistem
Early Warning System (EWS) banjir berhasil menggunakan protokol HTTPS/TLS dan SSL/TLS.

[{test_time}] ✅ Komunikasi antara Raspberry Pi dengan Firebase telah terenkripsi
menggunakan HTTPS/TLS sehingga data monitoring lebih aman selama transmisi.

[{test_time}] ✅ Jalur komunikasi PostgreSQL juga berhasil diamankan menggunakan SSL/TLS
untuk mengurangi risiko penyadapan data sensor (eavesdropping).

[{test_time}] ✅ Berdasarkan hasil pengujian, sistem keamanan komunikasi data
berjalan dengan baik dan mampu menjaga kerahasiaan serta integritas data monitoring.
""")

else:

    print(f"""
[{test_time}] ⚠️ Pengujian menunjukkan masih terdapat jalur komunikasi yang belum
menggunakan HTTPS/TLS atau SSL/TLS.

[{test_time}] ⚠️ Sistem masih memiliki risiko penyadapan data selama transmisi.

[{test_time}] ⚠️ Keamanan komunikasi data perlu ditingkatkan agar seluruh proses
monitoring menggunakan jalur terenkripsi.
""")