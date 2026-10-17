import sqlite3
import os

SOURCE_DB = "arena_helper.db"
TARGET_DB = "engine_graph.db"

def migrate_to_engine_graph():
    if not os.path.exists(SOURCE_DB) or not os.path.exists(TARGET_DB):
        print("[-] Error: Source or target database missing.")
        return

    src_conn = sqlite3.connect(SOURCE_DB)
    src_cur = src_conn.cursor()
    
    # Read staged collection data
    src_cur.execute("SELECT card_name, quantity, rarity FROM user_collection_staging")
    staged_rows = src_cur.fetchall()
    src_conn.close()

    if not staged_rows:
        print("[-] No staged cards found to migrate.")
        return

    tgt_conn = sqlite3.connect(TARGET_DB)
    tgt_cur = tgt_conn.cursor()

    # Check target table structure in engine_graph.db
    tgt_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_collection';")
    if not tgt_cur.fetchone():
        print("[-] Error: 'user_collection' table not found in engine_graph.db.")
        tgt_conn.close()
        return

    # Clear or sync into engine_graph.db's user_collection table
    # Let's inspect columns of user_collection first
    tgt_cur.execute("PRAGMA table_info(user_collection)")
    cols = [col[1] for col in tgt_cur.fetchall()]
    print(f"[+] Target 'user_collection' columns: {cols}")

    migrated_count = 0
    for card_name, quantity, rarity in staged_rows:
        try:
            # Adapt insert based on standard engine_graph schema (card_name, quantity, etc.)
            tgt_cur.execute("""
                INSERT OR REPLACE INTO user_collection (card_name, quantity)
                VALUES (?, ?)
            """, (card_name, quantity))
            migrated_count += 1
        except Exception as e:
            # Fallback or alternate column name handling if needed
            pass

    tgt_conn.commit()
    tgt_conn.close()
    print(f"[+] Successfully migrated {migrated_count} cards from staging into engine_graph.db user_collection.")

if __name__ == "__main__":
    migrate_to_engine_graph()
