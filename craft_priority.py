import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def generate_craft_priority_report():
    print("[*] Generating Craft Priority Report (Wildcard Optimization)...")
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

            # 3. Fetch all decks and their analysis scores
            decks_res = await session.execute(text("""
                SELECT d.id, d.name, d.format, da.final_score
                FROM decks d
                JOIN deck_analyses da ON da.deck_id = d.id;
            """))
            decks = decks_res.fetchall()

            # Map card_id -> list of unlocking opportunities
            card_opportunities = {}

            for deck in decks:
                deck_id = deck.id
                deck_name = deck.name
                deck_score = deck.final_score or 50.0

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

                for dc in deck_cards:
                    user_owned = user_collection.get(dc.id, 0)
                    needed = dc.quantity
                    if user_owned < needed:
                        deficit = needed - user_owned
                        rarity = (dc.rarity or "rare").lower()
                        is_mythic = any(m in rarity for m in ["mythic", "special", "masterpiece"])
                        card_rarity = "Mythic" if is_mythic else "Rare"

                        if dc.id not in card_opportunities:
                            card_opportunities[dc.id] = {
                                "card_name": dc.name,
                                "rarity": card_rarity,
                                "unlocks_decks": [],
                                "total_deficit": 0
                            }
                        
                        card_opportunities[dc.id]["unlocks_decks"].append({
                            "deck_name": deck_name,
                            "deficit": deficit,
                            "deck_score": deck_score
                        })
                        card_opportunities[dc.id]["total_deficit"] += deficit

            # Scoring & Ranking Craft Priorities
            # Craft Score = (Sum of Meta Scores of decks it helps complete) * (Number of decks unlocked) / (Cost)
            ranked_crafts = []
            for cid, info in card_opportunities.items():
                deck_count = len(info["unlocks_decks"])
                cumulative_deck_score = sum(d["deck_score"] for d in info["unlocks_decks"])
                cost = info["total_deficit"]
                
                # Weight score by meta value and breadth of unlocks, penalizing high costs slightly
                craft_score = (cumulative_deck_score * deck_count) / max(1, cost * 0.5)

                ranked_crafts.append({
                    "card_name": info["card_name"],
                    "rarity": info["rarity"],
                    "unlocks": info["unlocks_decks"],
                    "cost": cost,
                    "score": craft_score
                })

            # Sort by highest craft priority score
            ranked_crafts.sort(key=lambda x: x["score"], reverse=True)

            print("\n" + "="*50)
            print("--- CRAFT PRIORITY REPORT ---")
            print("="*50)

            for i, craft in enumerate(ranked_crafts[:5], 1):
                print(f"\n#{i} {craft['card_name']} ({craft['rarity']})")
                print(f"Unlocks / Helps Complete:")
                for u in craft["unlocks"]:
                    print(f"  • {u['deck_name']} (Needed: {u['deficit']}x)")
                print(f"Cost:")
                print(f"  • {craft['cost']} {craft['rarity']}")

            print("="*50 + "\n")

        except Exception as e:
            await session.rollback()
            print(f"[!] Error generating craft priority report: {e}")

if __name__ == "__main__":
    asyncio.run(generate_craft_priority_report())