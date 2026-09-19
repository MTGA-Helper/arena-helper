import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def generate_unlock_report():
    print("[*] Generating Deck Unlock Report V1...")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch active user ID
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

            # 4. Fetch all decks
            decks_res = await session.execute(text("""
                SELECT d.id, d.name, d.format, da.final_score
                FROM decks d
                JOIN deck_analyses da ON da.deck_id = d.id;
            """))
            decks = decks_res.fetchall()

            fully_buildable = []
            almost_buildable = []  # Missing <= 4 total wildcards
            close_calls = []       # Missing <= 8 total wildcards

            for deck in decks:
                deck_id = deck.id
                deck_name = deck.name
                final_score = deck.final_score or 50.0

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
                """), {"did": int(deck_id)})
                deck_cards = cards_res.fetchall()

                total_required = sum(dc.quantity for dc in deck_cards)
                owned_count = 0
                missing_rares = 0
                missing_mythics = 0

                for dc in deck_cards:
                    user_owned = user_collection.get(dc.id, 0)
                    needed = dc.quantity
                    if user_owned >= needed:
                        owned_count += needed
                    else:
                        owned_count += user_owned
                        deficit = needed - user_owned
                        rarity = (dc.rarity or "rare").lower()
                        if any(m in rarity for m in ["mythic", "special", "masterpiece"]):
                            missing_mythics += deficit
                        elif "rare" in rarity:
                            missing_rares += deficit

                completion = (owned_count / total_required * 100.0) if total_required > 0 else 0.0
                total_missing_wc = missing_rares + missing_mythics

                deck_info = {
                    "name": deck_name,
                    "format": deck.format,
                    "completion": round(completion, 1),
                    "missing_rares": missing_rares,
                    "missing_mythics": missing_mythics,
                    "score": round(final_score, 1)
                }

                if missing_rares == 0 and missing_mythics == 0:
                    fully_buildable.append(deck_info)
                elif total_missing_wc <= 4:
                    almost_buildable.append(deck_info)
                elif total_missing_wc <= 8:
                    close_calls.append(deck_info)

            # Print Categorized Report
            print("\n" + "="*60)
            print("--- DECK UNLOCK REPORT (ACTIONABLE INVENTORY) ---")
            print("="*60)

            print(f"\n🟢 FULLY BUILDABLE DECKS ({len(fully_buildable)} ready to play):")
            if fully_buildable:
                for d in fully_buildable:
                    print(f"  • {d['name']} ({d['format']}) - Meta Score: {d['score']}")
            else:
                print("  (None currently fully buildable)")

            print(f"\n🟡 ALMOST BUILDABLE DECKS (Missing ≤ 4 Wildcards):")
            if almost_buildable:
                for d in almost_buildable:
                    print(f"  • {d['name']} ({d['format']}) -> Missing Rares: {d['missing_rares']} | Mythics: {d['missing_mythics']}")
            else:
                print("  (None in this tier)")

            print(f"\n🟠 CLOSE CALLS (Missing ≤ 8 Wildcards):")
            if close_calls:
                for d in close_calls:
                    print(f"  • {d['name']} ({d['format']}) -> Missing Rares: {d['missing_rares']} | Mythics: {d['missing_mythics']}")
            else:
                print("  (None in this tier)")

            print("="*60 + "\n")

        except Exception as e:
            await session.rollback()
            print(f"[!] Error generating unlock report: {e}")

if __name__ == "__main__":
    asyncio.run(generate_unlock_report())