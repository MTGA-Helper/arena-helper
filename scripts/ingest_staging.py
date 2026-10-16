import csv
import sqlite3
import os

DB_PATH = "arena_helper.db"

def init_staging_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_collection_staging (
            card_name TEXT PRIMARY KEY,
            quantity INTEGER,
            rarity TEXT
        )
    """)
    conn.commit()
    conn.close()

def ingest_to_staging(csv_filename="collection.csv"):
    init_staging_table()
    if not os.path.exists(csv_filename):
        print(f"[-] Error: {csv_filename} not found. Place your collection export in the root directory.")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_collection_staging")

    total_cards = 0
    unique_cards = 0

    with open(csv_filename, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Fixed case sensitivity for actual CSV headers: Name, Count
            name = (
                row.get("Name")
                or row.get("name")
                or row.get("Card Name")
                or row.get("card_name")
            )
            qty_str = (
                row.get("Count")
                or row.get("count")
                or row.get("quantity")
                or row.get("qty")
                or "1"
            )
            
            try:
                qty = int(qty_str)
            except ValueError:
                qty = 1
                
            rarity = (row.get("rarity") or "common").lower()
            
            if name:
                name_clean = name.strip()
                cursor.execute("""
                    INSERT INTO user_collection_staging (card_name, quantity, rarity) 
                    VALUES (?, ?, ?)
                    ON CONFLICT(card_name) DO UPDATE SET quantity = quantity + ?
                """, (name_clean, qty, rarity, qty))
                total_cards += qty
                unique_cards += 1

    conn.commit()
    conn.close()
    print(f"[+] Staged successfully: {unique_cards} unique cards ({total_cards} total inventory).")
    return True

if __name__ == "__main__":
    ingest_to_staging()
