import sqlite3
import os

STAGING_DB = "arena_helper.db"
ENGINE_DB = "engine_graph.db"

def sync_engine_counts():
    if not os.path.exists(STAGING_DB) or not os.path.exists(ENGINE_DB):
        print("[-] Error: Staging or Engine database missing.")
        return

    # Read correct quantities from staging
    staging_conn = sqlite3.connect(STAGING_DB)
    staging_cur = staging_conn.cursor()
    staging_cur.execute("SELECT card_name, quantity FROM user_collection_staging")
    staged_records = staging_cur.fetchall()
    staging_conn.close()

    if not staged_records:
        print("[-] No records found in staging collection.")
        return

    # Update engine_graph.db user_collection with correct owned_count
    engine_conn = sqlite3.connect(ENGINE_DB)
    engine_cur = engine_conn.cursor()

    updated_count = 0
    for card_name, qty in staged_records:
        engine_cur.execute("""
            UPDATE user_collection 
            SET owned_count = ? 
            WHERE card_name = ?
        """, (qty, card_name))
        updated_count += engine_cur.rowcount

    engine_conn.commit()
    
    # Verify new total copies in engine db
    engine_cur.execute("SELECT SUM(owned_count) FROM user_collection")
    new_total = engine_cur.fetchone()[0]
    
    engine_conn.close()

    print("==========================================")
    print(" ENGINE COLLECTION QUANTITY SYNC REPORT")
    print("==========================================")
    print(f" Updated Records: {updated_count}")
    print(f" Engine Total Copies After Sync: {new_total}")
    print("==========================================")

if __name__ == "__main__":
    sync_engine_counts()
