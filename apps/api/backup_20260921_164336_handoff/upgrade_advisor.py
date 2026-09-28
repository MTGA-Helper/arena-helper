import asyncio
import sys
from sqlalchemy import text
from database import AsyncSessionLocal

async def get_deck_upgrade_advice(target_deck_name: str):
    async with AsyncSessionLocal() as session:
        # 1. Fetch user ID
        user_res = await session.execute(text("SELECT id FROM users LIMIT 1;"))
        user_row = user_res.fetchone()
        if not user_row:
            print("[!] No users found in database.")
            return
        user_id = str(user_row.id)

        # 2. Fetch user collection
        collection_res = await session.execute(text("""
            SELECT card_id, quantity FROM user_collections WHERE user_id::text = :uid;
        """), {"uid": user_id})
        user_collection = {row.card_id: row.quantity for row in collection_res.fetchall()}

        # 3. Fetch wildcard inventory
        available_rares = 20
        available_mythics = 8
        wc_res = await session.execute(text("""
            SELECT rare, mythic FROM wildcard_inventories WHERE user_id::text = :uid LIMIT 1;
        """), {"uid": user_id})
        wc_row = wc_res.fetchone()
        if wc_row:
            available_rares = wc_row.rare or 20
            available_mythics = wc_row.mythic or 8

        # 4. Find matching deck (case-insensitive substring match)
        deck_res = await session.execute(text("""
            SELECT id, name, format FROM decks WHERE LOWER(name) LIKE LOWER(:dname) LIMIT 1;
        """), {"dname": f"%{target_deck_name}%"})
        deck = deck_res.fetchone()

        if not deck:
            print(f"[!] Deck matching '{target_deck_name}' not found in corpus.")
            return

        print("\n" + "="*50)
        print(f"--- UPGRADE ADVISOR: {deck.name} ({deck.format}) ---")
        print("="*50)

        # 5. Fetch required cards for this deck
        cards_res = await session.execute(text("""
            SELECT 
                c.id, 
                c.name, 
                dc.quantity,
                cp.rarity
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            LEFT JOIN (
                SELECT DISTINCT ON (card_id) card_id, rarity
                FROM card_prints
            ) cp ON cp.card_id = c.id
            WHERE dc.deck_id = :did;
        """), {"did": int(deck.id)})
        deck_cards = cards_res.fetchall()

        missing_cards = []
        total_missing_rares = 0
        total_missing_mythics = 0

        for dc in deck_cards:
            user_owned = user_collection.get(dc.id, 0)
            needed = dc.quantity
            if user_owned < needed:
                deficit = needed - user_owned
                rarity = (dc.rarity or "rare").lower()
                
                is_mythic = any(m in rarity for m in ["mythic", "special", "masterpiece"])
                if is_mythic:
                    total_missing_mythics += deficit
                else:
                    total_missing_rares += deficit

                missing_cards.append({
                    "name": dc.name,
                    "deficit": deficit,
                    "rarity": "Mythic" if is_mythic else "Rare"
                })

        if not missing_cards:
            print("\n🟢 STATUS: 100% Buildable! You already own all required cards.")
        else:
            # Sort missing cards: Mythics first, then by highest deficit
            missing_cards.sort(key=lambda x: (x["rarity"] != "Mythic", -x["deficit"]))

            print("\nMissing Cards:")
            for mc in missing_cards:
                print(f"  • {mc['deficit']}x {mc['name']} ({mc['rarity']})")

            print(f"\nTotal Cost:")
            print(f"  • Rare Wildcards   : {total_missing_rares}")
            print(f"  • Mythic Wildcards : {total_missing_mythics}")

            # Craftability Check against inventory
            can_craft_rares = available_rares >= total_missing_rares
            can_craft_mythics = available_mythics >= total_missing_mythics

            if can_craft_rares and can_craft_mythics:
                status = "🟢 Craftable immediately with current wildcards!"
            else:
                status = "🟡 Needs more wildcards to complete full craft."
            print(f"\nStatus:\n  • {status}")

        print("="*50 + "\n")

if __name__ == "__main__":
    deck_query = sys.argv[1] if len(sys.argv) > 1 else "Dimir Midrange"
    asyncio.run(get_deck_upgrade_advice(deck_query))