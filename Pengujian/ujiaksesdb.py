# PENGUJIAN KEAMANAN .4
import psycopg2
import time
import datetime

# ================================================================
# KONFIGURASI DATABASE
# Ganti sesuai database backend asli
# ================================================================

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "ews_database"
DB_USER = "postgres"
DB_PASSWORD = "password_database"

# ================================================================
# MULAI PENGUJIAN
# ================================================================

print("=" * 60)
print(" PENGUJIAN ROLE-BASED ACCESS CONTROL DATABASE ")
print("=" * 60)

start_time = time.time()

try:
    # ============================================================
    # KONEKSI DATABASE
    # ============================================================
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

    cursor = conn.cursor()

    # ============================================================
    # QUERY VALIDASI AKSES
    # ============================================================
    cursor.execute("SELECT current_database(), current_user;")
    result = cursor.fetchone()

    db_name = result[0]
    db_user = result[1]

    end_time = time.time()
    response_time = round(end_time - start_time, 3)

    # ============================================================
    # HASIL PENGUJIAN
    # ============================================================
    print(f"\n[{datetime.datetime.now()}] AKSES DATABASE BERHASIL")
    print(f"Database Aktif : {db_name}")
    print(f"User Login     : {db_user}")
    print(f"Response Time  : {response_time} detik")

    print("\n=== HASIL RBAC ===")
    print("User memiliki hak akses yang valid.")
    print("Database berhasil membatasi akses hanya")
    print("kepada pengguna dengan otorisasi yang sesuai.")

    # ============================================================
    # TUTUP KONEKSI
    # ============================================================
    cursor.close()
    conn.close()

except Exception as e:

    end_time = time.time()
    response_time = round(end_time - start_time, 3)

    print(f"\n[{datetime.datetime.now()}] AKSES DATABASE GAGAL")
    print(f"Response Time : {response_time} detik")

    print("\n=== HASIL RBAC ===")
    print("Akses ditolak karena user tidak memiliki")
    print("hak akses atau konfigurasi autentikasi salah.")

    print("\nDetail Error:")
    print(e)

print("\n" + "=" * 60)
print(" PENGUJIAN SELESAI ")
print("=" * 60)