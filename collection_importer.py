import asyncio
import os
import csv
from sqlalchemy import text
from database import AsyncSessionLocal
import uuid

def normalize(name: str) -> str:
    """Normalize card name for robust matching against database records."""
    if not isinstance(name, str):
        return ""
    normalized = name.strip().lower().replace("’", "'")
    if normalized.startswith("a-"):
        normalized = normalized[2:]
    return normalized

async def import_collection_csv(csv_path: str = "collection.csv", user_id = None):
    print(f"[*] Starting Production Collection Import (Zero-Dependency) from {csv_path}...")
    if not os.path.exists(csv_path):
        print(f"[!] File not found: {csv_path}")
        return

    rows_data = []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'Name' in row and 'Count' in row:
                rows_data.append({"Name": row['Name'], "Count": int(row['Count'])})

    if not rows_data:
        print("[!] CSV must contain 'Name' and 'Count' columns and data rows.")
        return

    async with AsyncSessionLocal() as session:
        # 1. Resolve active user ID
        if not user_id:
            user_res = await session.execute(text("SELECT id FROM users LIMIT 1;"))
            user_row = user_res.fetchone()
            if user_row:
                user_id = user_row.id
            else:
                user_id = uuid.uuid4()
                await session.execute(text("""
                    INSERT INTO users (id, email, hashed_password) 
                    VALUES (:id, 'untapped_player@arena.local', 'hash');
                """), {"id": user_id})
                await session.commit()

        print(f"[*] Target User ID: {user_id}")

        # 2. Fetch all cards from database and build normalized lookup dictionary
        cards_res = await session.execute(text("SELECT id, name FROM cards;"))
        db_cards = {normalize(row.name): row.id for row in cards_res.fetchall()}

        matched_count = 0
        unmatched_count = 0
        total_copies_imported = 0
        unmatched_records = []

        for row in rows_data:
            raw_name = row['Name']
            count = row['Count']
            norm_name = normalize(raw_name)
            
            card_id = db_cards.get(norm_name)

            if card_id:
                # 3. Use UPSERT to update quantity on repeated imports
                await session.execute(text("""
                    INSERT INTO user_collections (user_id, card_id, quantity)
                    VALUES (:uid, :cid, :q)
                    ON CONFLICT (user_id, card_id) 
                    DO UPDATE SET quantity = EXCLUDED.quantity;
                """), {"uid": user_id, "cid": card_id, "q": count})
                matched_count += 1
                total_copies_imported += count
            else:
                unmatched_count += 1
                unmatched_records.append({"Name": raw_name, "Count": count})

        await session.commit()

        # 4. Export unmatched cards for corpus gap analysis
        if unmatched_records:
            with open("unmatched_cards.csv", mode='w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["Name", "Count"])
                writer.writeheader()
                writer.writerows(unmatched_records)

        total_records = len(rows_data)
        coverage = (matched_count / total_records * 100.0) if total_records > 0 else 0.0

        # 5. Store and Print Import Statistics
        print("\n" + "="*50)
        print("--- PRODUCTION COLLECTION IMPORT REPORT ---")
        print("="*50)
        print(f"Total CSV Records     : {total_records}")
        print(f"Matched Cards         : {matched_count}")
        print(f"Unmatched Cards       : {unmatched_count}")
        print(f"Coverage              : {coverage:.2f}%")
        print(f"Total Copies Imported : {total_copies_imported}")
        print(f"Audit Log Saved       : unmatched_cards.csv")
        print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(import_collection_csv())