import psycopg2

# ===== CONFIG =====
DB_NAME = "ews_db"
DB_USER = "ews_user"
DB_PASSWORD = "ews_pass"
DB_HOST = "localhost"
DB_PORT = 5432


def create_database():
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="postgres",  # ganti kalau beda
        host=DB_HOST,
        port=DB_PORT
    )
    conn.autocommit = True
    cur = conn.cursor()

    # cek & buat database
    cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
    exists = cur.fetchone()

    if not exists:
        cur.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"Database {DB_NAME} dibuat")
    else:
        print(f"Database {DB_NAME} sudah ada")

    cur.close()
    conn.close()


def create_tables():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user="postgres",
        password="postgres",  # ganti kalau beda
        host=DB_HOST,
        port=DB_PORT
    )

    cur = conn.cursor()

    # tabel sensor
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            temperature FLOAT,
            humidity FLOAT,
            water_level FLOAT,
            rainfall FLOAT,
            status VARCHAR(50)
        );
    """)

    # tabel prediksi ML
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            input_data JSONB,
            prediction VARCHAR(50),
            confidence FLOAT
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Tabel berhasil dibuat")


if __name__ == "__main__":
    try:
        create_database()
        create_tables()
        print("Setup DB selesai ✔")
    except Exception as e:
        print("ERROR:", e)