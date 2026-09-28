# arena_updater.py - Background Telemetry & Collection Sync Daemon
import sqlite3
import csv
from datetime import datetime
import os

DB_PATH = "engine_graph.db"
COLLECTION_PATH = "collection.csv"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_telemetry_tables():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. User Collection Table (Fed from collection.csv)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_collection (
        card_name TEXT PRIMARY KEY,
        owned_count INTEGER,
        last_updated TEXT
    );
    """)
    
    # 2. User Matches Table (Fed from Player.log telemetry)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deck_name TEXT,
        result TEXT,
        opponent_archetype TEXT,
        timestamp TEXT
    );
    """)
    
    # 3. User Engine Metrics Table (Computed personal model telemetry)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_engine_metrics (
        engine_id INTEGER PRIMARY KEY,
        sample_size INTEGER,
        win_rate REAL,
        subsystem_efficiency REAL,
        FOREIGN KEY(engine_id) REFERENCES engines(id)
    );
    """)
    
    conn.commit()
    conn.close()
    print("[INIT] Telemetry and collection tables verified.")

def sync_collection():
    if not os.path.exists(COLLECTION_PATH):
        print(f"[WARNING] Collection file '{COLLECTION_PATH}' not found. Skipping collection sync.")
        return

    conn = get_db()
    cursor = conn.cursor()
    
    timestamp = datetime.now().astimezone().isoformat()
    synced_count = 0
    
    with open(COLLECTION_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name") or row.get("card_name")
            count = row.get("Count") or row.get("owned_count")
            
            if name and count:
                cursor.execute("""
                INSERT INTO user_collection (card_name, owned_count, last_updated)
                VALUES (?, ?, ?)
                ON CONFLICT(card_name) DO UPDATE SET
                    owned_count = excluded.owned_count,
                    last_updated = excluded.last_updated
                """, (name.strip(), int(count), timestamp))
                synced_count += 1
                
    conn.commit()
    conn.close()
    print(f"[SYNC] Successfully synchronized {synced_count} cards from '{COLLECTION_PATH}' into user_collection.")

def run_updater():
    print("=========================================================")
    print(" ARENA HELPER: BACKGROUND UPDATER SERVICE (ADR-003)")
    print("=========================================================")
    init_telemetry_tables()
    sync_collection()
    print("[COMPLETE] Updater pipeline execution finished.")

if __name__ == "__main__":
    run_updater()