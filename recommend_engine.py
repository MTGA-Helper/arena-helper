import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def generate_recommendations():
    print("[*] Starting Recommendation Engine V1 (Normalized Rarity Mode)...")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch test user ID
            user_res = await session.execute(text("SELECT id FROM users LIMIT 1;"))
            user_row = user_res.fetchone()
            if not user_row:
                print("[!] No users found in database.")
                return
            
            user_id = str(user_row.id)
            print(f"[*] Evaluating recommendations for User ID: {user_id}")

            # 2. Fetch user collection mapping
            collection_res = await session.execute(text("""
                SELECT card_id, quantity FROM user_collections WHERE user_id::text = :uid;
            """), {"uid": user_id})
            user_collection = {row.card_id: row.quantity for row in collection_res.fetchall()}

            # 3. Wildcard inventory
            available_rares = 20
            available_mythics = 8
            wc_res = await session.execute(text("""
                SELECT rare, mythic FROM wildcard_inventories WHERE user_id::text = :uid LIMIT 1;
            """), {"uid": user_id})
            wc_row = wc_res.fetchone()
            if wc_row:
                available_rares = wc_row.rare or 20
                available_mythics = wc_row.mythic or 8

            print(f"[*] Loaded User Profile -> Owned Cards: {len(user_collection)} | Wildcards -> Rares: {available_rares}, Mythics: {available_mythics}")

            # 4. Fetch decks with analysis scores
            decks_res = await session.execute(text("""
                SELECT d.id, d.name, d.format, da.final_score
                FROM decks d
                JOIN deck_analyses da ON da.deck_id = d.id;
            """))
            decks = decks_res.fetchall()

            if not decks:
                print("[!] No analyzed decks found in corpus.")
                return

            recommendations = []

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
                        
                        # Normalized rarity classification
                        if any(m in rarity for m in ["mythic", "special", "masterpiece", "rare"]):
                            if "mythic" in rarity or "special" in rarity or "masterpiece" in rarity:
                                missing_mythics += deficit
                            else:
                                missing_rares += deficit

                # Completion Score
                completion_score = (owned_count / total_required * 100.0) if total_required > 0 else 0.0

                # Wildcard Efficiency Score
                rare_penalty = max(0, missing_rares - available_rares) * 5
                mythic_penalty = max(0, missing_mythics - available_mythics) * 8
                wildcard_cost_penalty = min(100.0, rare_penalty + mythic_penalty)
                wildcard_efficiency = max(0.0, 100.0 - wildcard_cost_penalty)

                # Recommendation Score V1
                recommendation_score = (
                    final_score * 0.50 +
                    completion_score * 0.35 +
                    wildcard_efficiency * 0.15
                )

                recommendations.append({
                    "deck": deck_name,
                    "format": deck.format,
                    "recommendation_score": round(recommendation_score, 2),
                    "analysis_score": round(final_score, 2),
                    "completion_score": round(completion_score, 1),
                    "missing_rares": missing_rares,
                    "missing_mythics": missing_mythics
                })

            recommendations.sort(key=lambda x: x["recommendation_score"], reverse=True)

            print("\n" + "="*50)
            print("--- PERSONALIZED DECK RECOMMENDATIONS (V1) ---")
            print("="*50)
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"#{i} {rec['deck']} ({rec['format']})")
                print(f"    Recommendation Score : {rec['recommendation_score']}")
                print(f"    Deck Analysis Score  : {rec['analysis_score']}")
                print(f"    Collection Match     : {rec['completion_score']}%")
                print(f"    Missing Wildcards    : Rare: {rec['missing_rares']} | Mythic: {rec['missing_mythics']}")
                print("-" * 50)

            print("\n--- TOP CRAFT RECOMMENDATIONS ---")
            craft_res = await session.execute(text("""
                SELECT c.name, m.format, m.appearance_rate, m.winrate
                FROM meta_card_stats m
                JOIN cards c ON c.id = m.card_id
                ORDER BY m.appearance_rate DESC, m.winrate DESC
                LIMIT 5;
            """))
            craft_rows = craft_res.fetchall()
            for i, craft in enumerate(craft_rows, 1):
                print(f"{i}. {craft.name:<25} | Format: {craft.format:<10} | Appearance: {craft.appearance_rate:.1f}% | Winrate: {craft.winrate:.1f}% | Craft Value: A+")
            print("="*50 + "\n")

        except Exception as e:
            await session.rollback()
            print(f"[!] Error generating recommendations: {e}")

if __name__ == "__main__":
    asyncio.run(generate_recommendations())