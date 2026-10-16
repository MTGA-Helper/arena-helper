import sqlite3

DB_PATH = "arena_helper.db"

def analyze_missing_playsets_detail():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT card_name, quantity, rarity 
        FROM user_collection_staging 
        WHERE quantity < 4 
        ORDER BY rarity DESC, quantity DESC, card_name ASC 
        LIMIT 40
    """)
    rows = cursor.fetchall()
    
    conn.close()
    
    print("==========================================")
    print(" NEAR-COMPLETE PLAYSETS (Detailed View)")
    print("==========================================")
    for card_name, qty, rarity in rows:
        missing = 4 - qty
        print(f" {card_name:<32} | Owned: {qty} | Missing: {missing} | Rarity: {rarity}")
    print("==========================================")

if __name__ == "__main__":
    analyze_missing_playsets_detail()
