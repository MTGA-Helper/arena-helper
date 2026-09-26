import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def seed_test_user():
    print("[*] Seeding Test User Collection & Wildcards...")
    async with AsyncSessionLocal() as session:
        try:
            user_id = 1

            # 1. Clear out any existing test data for user_id = 1
            await session.execute(text("DELETE FROM user_collections WHERE user_id::text = :uid;"), {"uid": str(user_id)})
            await session.execute(text("DELETE FROM wildcard_inventories WHERE user_id::text = :uid;"), {"uid": str(user_id)})
            await session.commit()

            # 2. Seed Wildcard Inventory (e.g., 12 Rare wildcards, 6 Mythic wildcards)
            await session.execute(text("""
                INSERT INTO wildcard_inventories (user_id, wildcard_rare, wildcard_mythic)
                VALUES (CAST(:uid AS INTEGER), :rares, :mythics);
            """), {"uid": user_id, "rares": 12, "mythics": 6})

            # 3. Pull a sample of cards required by Mono-Red Aggro and Azorius Control to simulate partial ownership
            # Let's grab cards from the database and give the user a realistic 75-80% collection match for Mono-Red
            cards_res = await session.execute(text("""
                SELECT c.id, c.name 
                FROM cards c
                JOIN deck_cards dc ON dc.card_id = c.id
                JOIN decks d ON d.id = dc.deck_id
                WHERE d.name IN ('Mono-Red Aggro', 'Azorius Control')
                LIMIT 10;
            """))
            sample_cards = cards_res.fetchall()

            seeded_count = 0
            for card in sample_cards:
                # Give 4 copies of some, 2 copies of others
                qty = 4 if seeded_count % 2 == 0 else 2
                await session.execute(text("""
                    INSERT INTO user_collections (user_id, card_id, quantity)
                    VALUES (CAST(:uid AS INTEGER), :card_id, :qty)
                    ON CONFLICT DO NOTHING;
                """), {"uid": user_id, "card_id": card.id, "qty": qty})
                seeded_count += 1

            await session.commit()
            print(f"[+] Successfully seeded test user profile with {seeded_count} owned card entries and 12 Rare / 6 Mythic wildcards!")

        except Exception as e:
            await session.rollback()
            print(f"[!] Error seeding test user: {e}")

if __name__ == "__main__":
    asyncio.run(seed_test_user())