import sqlite3
import csv
import os

DB_PATH = "engine_graph.db"
DATA_DIR = "data"

def is_legal(value):
    return str(value).strip().lower() in ("t", "true", "legal", "1", "yes")

def build_corrected_intelligence():
    cards_path = os.path.join(DATA_DIR, "cards.csv")
    prints_path = os.path.join(DATA_DIR, "card_prints.csv")
    legalities_path = os.path.join(DATA_DIR, "card_legalities.csv")
    tags_path = os.path.join(DATA_DIR, "card_tags.csv")

    print("[*] Loading master database files...")
    
    # 1. Cards: id -> name
    cards_map = {}
    with open(cards_path, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c_id = row.get("id")
            c_name = row.get("name")
            if c_id and c_name:
                cards_map[c_id] = c_name.strip()

    name_to_id = {name.lower(): c_id for c_id, name in cards_map.items()}

    # 2. Prints: card_id -> rarity
    card_rarities = {}
    with open(prints_path, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c_id = row.get("card_id")
            rarity = row.get("rarity")
            if c_id and rarity:
                card_rarities[c_id] = rarity.lower()

    # 3. Legalities: card_id -> dict of format statuses
    card_legalities = {}
    with open(legalities_path, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c_id = row.get("card_id")
            if c_id:
                card_legalities[c_id] = {
                    "standard": row.get("standard"),
                    "alchemy": row.get("alchemy"),
                    "explorer": row.get("explorer"),
                    "historic": row.get("historic")
                }

    # 4. Tags: card_id -> [tags]
    card_tags = {}
    with open(tags_path, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c_id = row.get("card_id")
            tag = row.get("tag")
            if c_id and tag:
                if c_id not in card_tags:
                    card_tags[c_id] = []
                card_tags[c_id].append(tag.lower())

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT card_name, owned_count FROM user_collection")
    user_collection = cursor.fetchall()
    conn.close()

    standard_legal_owned = 0
    historic_legal_owned = 0
    alchemy_legal_owned = 0
    explorer_legal_owned = 0
    mechanic_counts = {}
    rarity_counts = {"mythic": 0, "rare": 0, "uncommon": 0, "common": 0, "unknown": 0}

    for card_name, qty in user_collection:
        key = card_name.strip().lower()
        c_id = name_to_id.get(key)
        if c_id:
            rarity = card_rarities.get(c_id, "common")
            if rarity in rarity_counts:
                rarity_counts[rarity] += qty
            else:
                rarity_counts["unknown"] += qty

            leg = card_legalities.get(c_id, {})
            if is_legal(leg.get("standard")):
                standard_legal_owned += qty
            if is_legal(leg.get("historic")):
                historic_legal_owned += qty
            if is_legal(leg.get("alchemy")):
                alchemy_legal_owned += qty
            if is_legal(leg.get("explorer")):
                explorer_legal_owned += qty

            for t in card_tags.get(c_id, []):
                mechanic_counts[t] = mechanic_counts.get(t, 0) + qty

    sorted_mechanics = sorted(mechanic_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    print("\n==========================================")
    print(" CORRECTED COLLECTION INTELLIGENCE REPORT")
    print("==========================================")
    print(f" Total Unique Cards Staged : {len(user_collection)}")
    print(f" Standard-Legal Copies     : {standard_legal_owned}")
    print(f" Historic-Legal Copies     : {historic_legal_owned}")
    print(f" Alchemy-Legal Copies      : {alchemy_legal_owned}")
    print(f" Explorer-Legal Copies     : {explorer_legal_owned}")
    print("------------------------------------------")
    print(" Total Copies by Rarity:")
    for r, total in rarity_counts.items():
        print(f"   {r.capitalize():<10}: {total} copies")
    print("------------------------------------------")
    print(" Top Supported Mechanics & Tags (by Copy Weight):")
    for tag, count in sorted_mechanics:
        print(f"   {tag.capitalize():<18}: {count} relevant copies")
    print("==========================================")

if __name__ == "__main__":
    build_corrected_intelligence()
