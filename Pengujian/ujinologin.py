# PENGUJIAN KEAMANAN .5
import requests
import datetime
import time

# ================================================================
# KONFIGURASI TARGET
# Ganti sesuai URL dashboard backend/frontend asli
# ================================================================

TARGET_URL = "https://makesens-kali.my.id/dashboard"

# ================================================================
# MULAI PENGUJIAN
# ================================================================

print("=" * 60)
print(" PENGUJIAN AKSES TANPA LOGIN ")
print("=" * 60)

start_time = time.time()

try:

    # ============================================================
    # REQUEST TANPA LOGIN
    # Tidak memakai session/cookie/token
    # ============================================================

    response = requests.get(
        TARGET_URL,
        allow_redirects=False,
        timeout=10
    )

    end_time = time.time()
    response_time = round(end_time - start_time, 3)

    status_code = response.status_code

    print(f"\n[{datetime.datetime.now()}]")
    print(f"Target URL     : {TARGET_URL}")
    print(f"HTTP Status    : {status_code}")
    print(f"Response Time  : {response_time} detik")

    # ============================================================
    # VALIDASI KEAMANAN
    # ============================================================

    if status_code in [301, 302]:

        redirect_url = response.headers.get("Location", "Tidak diketahui")

        print(f"Redirect Login : {redirect_url}")

        print("\n=== HASIL PENGUJIAN ===")
        print("AKSES DITOLAK")
        print("Sistem berhasil mengarahkan pengguna")
        print("ke halaman login sebelum mengakses dashboard.")

    elif status_code in [401, 403]:

        print("\n=== HASIL PENGUJIAN ===")
        print("AKSES DITOLAK")
        print("Sistem berhasil memblokir akses")
        print("tanpa autentikasi.")

    elif status_code == 200:

        print("\n=== HASIL PENGUJIAN ===")
        print("PERINGATAN KEAMANAN")
        print("Dashboard dapat diakses tanpa login.")
        print("Proteksi autentikasi belum berjalan dengan baik.")

    else:

        print("\n=== HASIL PENGUJIAN ===")
        print("Response tidak dikenali.")
        print("Perlu pemeriksaan konfigurasi sistem.")

except Exception as e:

    print(f"\n[{datetime.datetime.now()}]")
    print("Pengujian gagal dijalankan.")

    print("\nDetail Error:")
    print(e)

print("\n" + "=" * 60)
print(" PENGUJIAN SELESAI ")
print("=" * 60)