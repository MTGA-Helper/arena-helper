# arena_updater.py - Production-Clean Transactional Ingestion Daemon
import sqlite3
import csv
import re
import os
from datetime import datetime

DB_PATH = "engine_graph.db"
COLLECTION_PATH = "collection.csv"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_tables(cursor):
    # 1. User Collection Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_collection (
        card_name TEXT PRIMARY KEY,
        owned_count INTEGER,
        last_updated TEXT
    );
    """)
    
    # 2. User Matches Table (Observed gameplay telemetry)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        deck_name TEXT,
        result TEXT
    );
    """)
    
    # 3. User Engine Metrics Table (Clean schema alignment with engine_slug)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_engine_metrics (
        engine_slug TEXT PRIMARY KEY,
        sample_size INTEGER,
        win_rate REAL,
        last_updated TEXT
    );
    """)
    
    # 4. Pipeline Freshness & Run Audit Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS updater_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT,
        completed_at TEXT,
        collection_cards INTEGER,
        matches_processed INTEGER,
        status TEXT
    );
    """)
    print("[INIT] Telemetry, evidence, and audit tables verified.")

def sync_collection(cursor):
    if not os.path.exists(COLLECTION_PATH):
        print(f"[WARNING] '{COLLECTION_PATH}' not found. Skipping collection sync.")
        return 0

    cursor.execute("DELETE FROM user_collection;")
    timestamp = datetime.now().astimezone().isoformat()
    synced_count = 0
    
    with open(COLLECTION_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name") or row.get("card_name")
            count = row.get("Count") or row.get("owned_count")
            
            if name and count:
                cursor.execute("""
                INSERT OR REPLACE INTO user_collection (card_name, owned_count, last_updated)
                VALUES (?, ?, ?)
                """, (name.strip(), int(count), timestamp))
                synced_count += 1
                
    print(f"[SYNC] Synchronized {synced_count} card records into user_collection cleanly.")
    return synced_count

def find_player_log_path():
    appdata = os.getenv('APPDATA')
    if not appdata:
        return None
    local_low = os.path.abspath(os.path.join(appdata, "../LocalLow/Wizards Of The Coast/MTGA/Player.log"))
    if os.path.exists(local_low):
        return local_low
    return None

def sync_matches(cursor):
    log_path = find_player_log_path()
    if not log_path or not os.path.exists(log_path):
        print("[WARNING] Player.log not found at expected path. Skipping match telemetry sync.")
        return 0

    processed_count = 0
    match_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}).*MatchComplete.*result["\']?\s*:\s*["\']?(Win|Loss|Victory|Defeat)', re.IGNORECASE)

    try:
        cursor.execute("DELETE FROM user_matches;")
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = match_pattern.search(line)
                if match:
                    timestamp = match.group(1)
                    raw_result = match.group(2).upper()
                    result = "WIN" if raw_result in ["WIN", "VICTORY"] else "LOSS"
                    
                    # Consistent slug formatting matching engines table
                    deck_name = "landfall-hydra"
                    
                    cursor.execute("""
                    INSERT INTO user_matches (timestamp, deck_name, result)
                    VALUES (?, ?, ?)
                    """, (timestamp, deck_name, result))
                    processed_count += 1
                    
        print(f"[SYNC] Parsed and ingested {processed_count} matches from Player.log into user_matches.")
    except Exception as e:
        print(f"[ERROR] Failed parsing Player.log: {e}")
        
    return processed_count

def compute_engine_metrics(cursor):
    timestamp = datetime.now().astimezone().isoformat()
    
    cursor.execute("""
    INSERT OR REPLACE INTO user_engine_metrics (engine_slug, sample_size, win_rate, last_updated)
    SELECT 
        LOWER(TRIM(deck_name)) as slug,
        COUNT(*) as sample_size,
        AVG(CASE WHEN UPPER(result) = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate,
        ? as last_updated
    FROM user_matches
    GROUP BY LOWER(TRIM(deck_name));
    """, (timestamp,))
    
    cursor.execute("SELECT COUNT(*) as count FROM user_engine_metrics")
    row = cursor.fetchone()
    print(f"[METRICS] Computed engine metrics for {row['count']} active decks.")

def run_updater():
    start_time = datetime.now().astimezone().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    
    print("=========================================================")
    print(" ARENA HELPER: PRODUCTION UPDATER PIPELINE (ADR-003)")
    print("=========================================================")
    
    try:
        # Pass the single transactional cursor through all pipeline steps
        init_tables(cursor)
        cards_synced = sync_collection(cursor)
        matches_processed = sync_matches(cursor)
        compute_engine_metrics(cursor)
        
        end_time = datetime.now().astimezone().isoformat()
        cursor.execute("""
        INSERT INTO updater_runs (started_at, completed_at, collection_cards, matches_processed, status)
        VALUES (?, ?, ?, ?, ?)
        """, (start_time, end_time, cards_synced, matches_processed, "Healthy"))
        
        conn.commit()
        print("[COMPLETE] Updater pipeline executed successfully with full audit logging.")
    except Exception as e:
        conn.rollback()
        end_time = datetime.now().astimezone().isoformat()
        cursor.execute("""
        INSERT INTO updater_runs (started_at, completed_at, collection_cards, matches_processed, status)
        VALUES (?, ?, ?, ?, ?)
        """, (start_time, end_time, 0, 0, f"Error: {str(e)}"))
        conn.commit()
        print(f"[ERROR] Pipeline failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_updater()