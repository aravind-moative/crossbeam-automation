import sqlite3

# Replace with your actual SQLite database file path
DB_PATH = 'scoring_weights.db'

def list_records_and_schema():
    # Connect to the SQLite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("=== Table Schema ===")
        cursor.execute("PRAGMA table_info(crossbeam_records);")
        schema = cursor.fetchall()
        for column in schema:
            cid, name, col_type, notnull, dflt_value, pk = column
            print(f"{name} ({col_type}){' PRIMARY KEY' if pk else ''}")

        print("\n=== Table Records ===")
        cursor.execute("SELECT * FROM crossbeam_records;")
        rows = cursor.fetchall()
        for row in rows:
            print(row)

    except sqlite3.Error as e:
        print("SQLite error:", e)

    finally:
        conn.close()

if __name__ == "__main__":
    list_records_and_schema()
