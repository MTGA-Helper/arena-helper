import sqlite3

DB_PATH = "arena_helper.db"

def analyze_ownership():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM user_collection_staging")
    unique_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(quantity) FROM user_collection_staging")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM user_collection_staging WHERE quantity >= 4")
    playsets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM user_collection_staging WHERE quantity = 3")
    three_ofs = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM user_collection_staging WHERE quantity = 2")
    two_ofs = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM user_collection_staging WHERE quantity = 1")
    singletons = cursor.fetchone()[0]
    
    conn.close()
    
    print("==========================================")
    print(" COLLECTION OWNERSHIP INTELLIGENCE REPORT")
    print("==========================================")
    print(f" Unique Cards: {unique_count}")
    print(f" Total Copies: {total_count}")
    print("------------------------------------------")
    print(f" Playsets (4+ copies): {playsets}")
    print(f" Three-ofs (3 copies): {three_ofs}")
    print(f" Two-ofs (2 copies):   {two_ofs}")
    print(f" Singletons (1 copy):  {singletons}")
    print("==========================================")

if __name__ == "__main__":
    analyze_ownership()
