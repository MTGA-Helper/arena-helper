import os
import sqlite3
import glob

print("=======================================================")
print(" ARENA HELPER DATABASE & TABLE AUDIT")
print("=======================================================")

databases = glob.glob("**/*.db", recursive=True)
print(f"Found databases: {databases}")

for db in databases:
    print(f"\n[+] Inspecting: {db}")
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"    Tables: {tables}")
        
        if 'matches' in tables:
            cursor.execute("SELECT COUNT(*) FROM matches;")
            print(f"    Match rows: {cursor.fetchone()[0]}")
        conn.close()
    except Exception as e:
        print(f"    Error reading {db}: {e}")

print("=======================================================")
