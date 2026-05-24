# MONITORING SISTEM .2
import psycopg2

# =====================================================
# KONEKSI DATABASE
# =====================================================
conn = psycopg2.connect(
    host="localhost",
    database="ews_banjir",
    user="pi",
    password="ews"
)

cur = conn.cursor()

print("✅ Database Connected")

# =====================================================
# AMBIL DATA TERBARU DARI DATABASE
# =====================================================
try:
    cur.execute("""
    SELECT * FROM sensor_log
    ORDER BY id DESC
    LIMIT 10
    """)

    hasil = cur.fetchall()

    print("\n📋 DATA SENSOR TERBARU:")
    print("=" * 100)

    for row in hasil:
        print(f"""
ID              : {row[0]}
Waktu           : {row[1]}
Suhu            : {row[2]}
Kelembapan      : {row[3]}
Tekanan         : {row[4]}
Jarak Air       : {row[5]}
Flow            : {row[6]}
Rain Total      : {row[7]}
Rain Rate       : {row[8]}
Float Level     : {row[9]}
Alert           : {row[10]}
Sequence        : {row[11]}
RSSI            : {row[12]}
        """)
        print("-" * 100)

    print("✅ Data berhasil dibaca dari database")

    # =====================================================
    # SUMMARY
    # =====================================================
    print("\n📊 SUMMARY PENGUJIAN")
    print("=" * 100)

    total_data = len(hasil)

    if total_data > 0:
        latest = hasil[0]

        print(f"Jumlah Data Ditampilkan : {total_data}")
        print(f"Data Terbaru ID         : {latest[0]}")
        print(f"Waktu Data Terbaru      : {latest[1]}")
        print(f"Status Penyimpanan      : BERHASIL")
        print(f"Kondisi Database        : NORMAL")
        print(f"Kesimpulan              : Data sensor berhasil tersimpan dan dapat dibaca dari database PostgreSQL.")

    else:
        print("⚠️ Tidak ada data pada database")

except Exception as e:
    print("❌ Gagal membaca data dari database")
    print("Error:", e)

# =====================================================
# TUTUP KONEKSI
# =====================================================
cur.close()
conn.close()

print("\n🔒 Koneksi database ditutup")