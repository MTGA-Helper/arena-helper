import sqlite3

DB_PATH = "arena_helper.db"

def analyze_missing_playsets():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find cards where quantity < 4, sorted by how close they are or highest count first
    cursor.execute("""
        SELECT card_name, quantity, rarity 
        FROM user_collection_staging 
        WHERE quantity < 4 
        ORDER BY quantity DESC, card_name ASC 
        LIMIT 25
    """)
    rows = cursor.fetchall()
    
    conn.close()
    
    print("==========================================")
    print(" NEAR-COMPLETE PLAYSETS (Top 25 by Quantity)")
    print("==========================================")
    for card_name, qty, rarity in rows:
        missing = 4 - qty
        print(f" {card_name:<30} | Owned: {qty} | Missing: {missing} | ({rarity})")
    print("==========================================")

if __name__ == "__main__":
    analyze_missing_playsets()
