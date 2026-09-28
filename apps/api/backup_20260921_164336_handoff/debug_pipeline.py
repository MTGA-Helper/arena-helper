import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal
import uuid

async def diagnose_and_fix():
    print("[*] --- RUNNING DIAGNOSTIC & REPAIR PIPELINE ---")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Check Deck Card Counts (Debugging Inflated Costs)
            print("\n[*] 1. Inspecting Deck Sizes & Card Rows...")
            deck_sizes = await session.execute(text("""
                SELECT 
                    d.name,
                    COUNT(dc.id) AS card_rows,
                    SUM(dc.quantity) AS total_cards
                FROM decks d
                JOIN deck_cards dc ON dc.deck_id = d.id
                GROUP BY d.name
                ORDER BY total_cards DESC;
            """))
            for row in deck_sizes.fetchall():
                print(f"  -> Deck: {row.name:<25} | Rows: {row.card_rows:<5} | Total Quantity: {row.total_cards}")

            # 2. Check for duplicate card_id entries per deck
            print("\n[*] 2. Checking for Duplicate Deck-Card Mappings...")
            dupes = await session.execute(text("""
                SELECT deck_id, card_id, COUNT(*)
                FROM deck_cards
                GROUP BY deck_id, card_id
                HAVING COUNT(*) > 1;
            """))
            dupe_rows = dupes.fetchall()
            print(f"  -> Duplicate deck_cards rows found: {len(dupe_rows)}")

            # 3. Ensure a valid test user and seed collections directly matching active user ID
            print("\n[*] 3. Provisioning & Seeding Test User Collection...")
            user_res = await session.execute(text("SELECT id FROM users LIMIT 1;"))
            user_row = user_res.fetchone()
            
            if user_row:
                user_id = user_row.id
            else:
                user_id = uuid.uuid4()
                await session.execute(text("""
                    INSERT INTO users (id, email, hashed_password) 
                    VALUES (:id, 'test@arena.local', 'placeholder');
                """), {"id": user_id})
                await session.commit()

            print(f"  -> Active Test User ID: {user_id}")

            # Clean seed user_collections and wildcard_inventories
            await session.execute(text("DELETE FROM user_collections WHERE user_id = :uid;"), {"uid": user_id})
            await session.execute(text("DELETE FROM wildcard_inventories WHERE user_id = :uid;"), {"uid": user_id})
            await session.commit()

            # Seed Wildcards
            try:
                await session.execute(text("""
                    INSERT INTO wildcard_inventories (user_id, rare, mythic) 
                    VALUES (:uid, 20, 8);
                """), {"uid": user_id})
            except Exception:
                await session.rollback()
                await session.execute(text("""
                    INSERT INTO wildcard_inventories (user_id, wildcard_rare, wildcard_mythic) 
                    VALUES (:uid, 20, 8);
                """), {"uid": user_id})

            # Seed a robust test collection (give 4x copies of ALL cards in Mono-Red Aggro and 2x across others)
            cards_res = await session.execute(text("""
                SELECT DISTINCT c.id, d.name AS deck_name
                FROM cards c
                JOIN deck_cards dc ON dc.card_id = c.id
                JOIN decks d ON d.id = dc.deck_id
                WHERE d.name IN ('Mono-Red Aggro', 'Boros Aggro', 'Dimir Midrange');
            """))
            cards = cards_res.fetchall()

            seeded = 0
            for card in cards:
                qty = 4 if card.deck_name in ('Mono-Red Aggro', 'Boros Aggro') else 2
                await session.execute(text("""
                    INSERT INTO user_collections (user_id, card_id, quantity)
                    VALUES (:uid, :cid, :q);
                """), {"uid": user_id, "cid": card.id, "q": qty})
                seeded += 1

            await session.commit()
            print(f"  -> Successfully seeded {seeded} collection records for user {user_id}.")

            # 4. Verify collection count in DB
            count_res = await session.execute(text("SELECT COUNT(*) FROM user_collections WHERE user_id = :uid;"), {"uid": user_id})
            print(f"  -> Total rows in user_collections for this user: {count_res.scalar()}")

        except Exception as e:
            await session.rollback()
            print(f"[!] Diagnostic error: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_and_fix())