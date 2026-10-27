import sqlite3
import os

DB_PATH = "arena_helper.db"

def resolve_collection():
    if not os.path.exists(DB_PATH):
        print(f"[-] Error: Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if 'cards' table exists in main db
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cards';")
    cards_table_exists = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM user_collection_staging")
    staged_count = cursor.fetchone()[0]
    
    if not cards_table_exists:
        print("[-] Warning: 'cards' intelligence table not found in arena_helper.db.")
        print(f"[+] Staged Unique Cards: {staged_count}")
        conn.close()
        return

    # Perform resolution join against the master cards catalog
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN c.name IS NOT NULL THEN 1 ELSE 0 END) as matched,
            SUM(CASE WHEN c.name IS NULL THEN 1 ELSE 0 END) as unmatched
        FROM user_collection_staging sc
        LEFT JOIN cards c ON LOWER(TRIM(sc.card_name)) = LOWER(TRIM(c.name))
    """)
    res = cursor.fetchone()
    matched = res[0] or 0
    unmatched = res[1] or 0
    
    resolution_rate = round((matched / staged_count) * 100, 2) if staged_count > 0 else 0.0

    conn.close()

    print("==========================================")
    print(" COLLECTION RESOLUTION REPORT")
    print("==========================================")
    print(f" Staged Unique Cards: {staged_count}")
    print(f" Matched Catalog Cards: {matched}")
    print(f" Unmatched Cards:       {unmatched}")
    print(f" Resolution Rate:       {resolution_rate}%")
    print("==========================================")

if __name__ == "__main__":
    resolve_collection()
