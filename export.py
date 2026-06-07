from sqlalchemy import create_engine
import pandas as pd

engine = create_engine(
    "postgresql://pi:ews@localhost:5432/ews_banjir"
)

df = pd.read_sql(
    "SELECT * FROM sensor_log",
    engine
)

df.to_csv(
    "sensor_data.csv",
    index=False
)

print("CSV berhasil dibuat")