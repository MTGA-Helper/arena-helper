import sqlite3
import csv
import os

DB_PATH = "engine_graph.db"
DATA_DIR = "data"

def resolve_and_enrich():
    if not os.path.exists(DB_PATH):
        print(f"[-] Error: {DB_PATH} not found.")
        return

    cards_csv_path = os.path.join(DATA_DIR, "cards.csv")
    prints_csv_path = os.path.join(DATA_DIR, "card_prints.csv")
    legalities_csv_path = os.path.join(DATA_DIR, "card_legalities.csv")

    if not os.path.exists(cards_csv_path) or not os.path.exists(prints_csv_path):
        print("[-] Error: Master CSV files missing in 'data/' directory.")
        return

    print("[*] Loading master cards catalog into memory...")
    master_cards = {}
    with open(cards_csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # cards.csv columns typically include id, name, mana_value, etc.
            card_id = row.get("id")
            name = row.get("name")
            if name:
                master_cards[name.strip().lower()] = {
                    "id": card_id,
                    "mana_value": row.get("mana_value") or 0.0,
                    "oracle_text": row.get("oracle_text") or ""
                }

    print(f"[*] Loaded {len(master_cards)} cards from master catalog.")

    print("[*] Loading card prints for rarity mapping...")
    card_rarities = {}
    with open(prints_csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            card_id = row.get("card_id")
            rarity = row.get("rarity")
            if card_id and rarity:
                card_rarities[card_id] = rarity.lower()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Pull user's collection from engine_graph
    cursor.execute("SELECT card_name, owned_count FROM user_collection")
    user_items = cursor.fetchall()

    matched = 0
    unmatched = 0
    rarity_breakdown = {"mythic": 0, "rare": 0, "uncommon": 0, "common": 0, "unknown": 0}

    for card_name, qty in user_items:
        key = card_name.strip().lower()
        if key in master_cards:
            matched += 1
            c_info = master_cards[key]
            c_id = c_info["id"]
            rarity = card_rarities.get(c_id, "common")
            if rarity in rarity_breakdown:
                rarity_breakdown[rarity] += 1
            else:
                rarity_breakdown["unknown"] += 1
        else:
            unmatched += 1

    conn.close()

    print("\n==========================================")
    print(" MASTER CATALOG RESOLUTION & ENRICHMENT")
    print("==========================================")
    print(f" Total User Unique Cards: {len(user_items)}")
    print(f" Matched to Master Catalog: {matched}")
    print(f" Unmatched Cards:          {unmatched}")
    print("------------------------------------------")
    print(" Rarity Distribution (Matched Unique Cards):")
    for r, count in rarity_breakdown.items():
        print(f"   {r.capitalize():<10}: {count}")
    print("==========================================")

if __name__ == "__main__":
    resolve_and_enrich()
