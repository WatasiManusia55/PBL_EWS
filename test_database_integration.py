from database import DatabaseManager

db = DatabaseManager()

success = 0
failed = 0

while True:

    latest = db.sensor_log()

    if latest:

        try:

            test_id = db.insert_sensor_data(
                latest["node_id"],
                latest["water_level"],
                latest["rainfall"],
                latest["battery"]
            )

            success += 1

            print(
                f"[OK] Insert ID={test_id} "
                f"Success={success}"
            )

        except Exception as e:

            failed += 1

            print(
                f"[FAILED] {e} "
                f"Failed={failed}"
            )

    time.sleep(60)