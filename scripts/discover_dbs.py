import os
import sqlite3

def find_databases():
    print("==========================================")
    print(" SCANNING FOR LOCAL DATABASES (.db, .sqlite)")
    print("==========================================")
    
    found_dbs = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith((".db", ".sqlite", ".sqlite3")):
                full_path = os.path.join(root, file)
                found_dbs.append(full_path)
                
    # Also check parent directory or common locations if needed
    parent_dir = os.path.abspath(os.path.join(".."))
    for file in os.listdir(parent_dir):
        if file.endswith((".db", ".sqlite", ".sqlite3")):
            found_dbs.append(os.path.abspath(os.path.join(parent_dir, file)))

    for db in found_dbs:
        print(f"\n[+] Found Database: {db}")
        try:
            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            print(f"    Tables: {tables}")
        except Exception as e:
            print(f"    [-] Error reading database: {e}")
    print("==========================================")

if __name__ == "__main__":
    find_databases()
