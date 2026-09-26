# test_db.py
import sqlite3

db_path = "engine_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
""")

tables = cursor.fetchall()
print(f"Successfully connected to '{db_path}'!")
print("Found tables:")
for row in tables:
    print(f" - {row[0]}")

conn.close()