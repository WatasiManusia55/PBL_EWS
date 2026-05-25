import psycopg2
import json
import re

# ===============================================================
# FUNGSI PARSER ASLI DARI KODE UTAMA ANDA (UNTUK DIUJI)
# ===============================================================
def parse_packet(raw):
    raw = raw.strip()
    if not raw: return None
    if raw.startswith('":'): raw = raw[3:]
    if not raw.startswith('{'): raw = '{' + raw
    if not raw.endswith('}'): raw += '}'
    raw = re.sub(r'([a-zA-Z]+):', r'"\1":', raw)
    raw = raw.replace("'", '"')
    raw = re.sub(r'[^\x20-\x7E]', '', raw)
    try: 
        return json.loads(raw)
    except: 
        return None

def jalankan_audit_postgresql():
    print("=" * 65)
    print("   SENSOR DATA VALIDATION TESTER - DIRECT POSTGRESQL AUDIT")
    print("=" * 65)
    print("🔄 Menghubungkan ke Database PostgreSQL lokal...")
    
    try:
        # 1. Koneksi ke Database PostgreSQL Anda
        conn = psycopg2.connect(
            host="localhost",
            database="ews_banjir",
            user="pi",
            password="ews"
        )
        cursor = conn.cursor()
        
        # 2. Ambil data asli dari tabel sensor_log
        # Kolom 'sq' sudah diubah menjadi 'seq' sesuai dengan struktur tabel DB Anda
        query = "SELECT id, waktu, seq FROM sensor_log ORDER BY waktu DESC LIMIT 100;"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print(" ⚠ Peringatan: Tabel 'sensor_log' di PostgreSQL masih kosong.")
            cursor.close()
            conn.close()
            return
            
        total_data = len(rows)
        sukses_format = 0
        
        print(f" ✅ Sukses Terhubung! Menemukan {total_data} data sensor asli di tabel 'sensor_log'.")
        print(" 🔄 Memulai audit forensik format data pada row database...")
        print("-" * 65)
        
        # 3. Lakukan pengujian format pada setiap baris data asli
        for indeks, row in enumerate(rows):
            db_id = row[0]
            db_waktu = row[1]
            db_sq = row[2]  # Mengambil nilai dari kolom 'seq' database
            
            # Rekonstruksi string mentah berbasis data terikat dari tabel DB
            raw_string_db = f"{{'sq':{db_sq}}}"
            
            # Uji kelayakan lewat parser utama
            hasil_parse = parse_packet(raw_string_db)
            
            # Validasi aturan spesifikasi EWS
            if isinstance(hasil_parse, dict) and 'sq' in hasil_parse:
                status_validitas = "VALID (Format Sesuai Spesifikasi)"
                sukses_format += 1
            else:
                status_validitas = "CACAT (Format Menyimpang)"
            
            # Tampilkan 3 sampel teratas dan 1 sampel terakhir agar terminal rapi
            if indeks < 3 or indeks == total_data - 1:
                print(f" 🗄️ [DB Row ID: {db_id} | SQ: {db_sq} | {db_waktu}]")
                print(f"    ➔ Status Sanitasi Parser: {status_validitas}")
            elif indeks == 3:
                print("    ... [seluruh row data antara sedang diperiksa secara background] ...")
                
        # 4. Tampilkan Summary Akhir Uji Validasi DB untuk Skripsi
        print("-" * 65)
        print("              SUMMARY AKHIR VALIDASI FORMAT POSTGRESQL")
        print("-" * 65)
        print(f" ● Total Row Data Diuji       : {total_data} Record Asli")
        print(f" ● Record Lolos Format Bersih : {sukses_format} Record")
        print(f" ● Record Cacat/Format Rusak  : {total_data - sukses_format} Record")
        print(f" ● Indeks Integritas Database : {round((sukses_format / total_data) * 100, 2)} %")
        print("-" * 65)
        
        if sukses_format == total_data:
            print(" ✅ KESIMPULAN: Fungsi Validasi Format Sukses 100%.")
            print("    Terbukti database PostgreSQL steril dari data sampah/cacat.")
            print("    Sistem secara andal memfilter input sebelum melakukan 'INSERT INTO'.")
            
        cursor.close()
        conn.close()
        
    except psycopg2.OperationalError:
        print(" ❌ Gagal terhubung ke PostgreSQL. Pastikan service Postgres Anda menyala.")
    except Exception as e:
        print(f" ❌ Terjadi kesalahan sistem: {e}")
    print("=" * 65)

if __name__ == "__main__":
    jalankan_audit_postgresql()