import sqlite3

DB_PATH = "engine_graph.db"

def inspect_engine_collection():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check table info for user_collection
    cursor.execute("PRAGMA table_info(user_collection)")
    columns = [col[1] for col in cursor.fetchall()]
    print("[+] user_collection columns:", columns)
    
    # Show first 10 rows
    cursor.execute("SELECT * FROM user_collection LIMIT 10")
    rows = cursor.fetchall()
    
    conn.close()
    
    print("\n==========================================")
    print(" ENGINE_GRAPH.DB user_collection (First 10)")
    print("==========================================")
    for row in rows:
        print(row)
    print("==========================================")

if __name__ == "__main__":
    inspect_engine_collection()
