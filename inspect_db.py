# inspect_db.py
import sqlite3

conn = sqlite3.connect("engine_graph.db")
print("Engine Columns:")
for col in conn.execute("PRAGMA table_info(engines)"):
    print(f" - {col[1]} ({col[2]})")

print("\nSeeded Rows:")
for row in conn.execute("SELECT slug, name, status FROM engines"):
    print(row)

conn.close()