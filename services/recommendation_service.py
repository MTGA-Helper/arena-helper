from sqlalchemy import text
from database import AsyncSessionLocal

async def fetch_recommendations():
    async with AsyncSessionLocal() as session:
        user_res = await session.execute(text("SELECT id FROM users LIMIT 1;"))
        user_row = user_res.fetchone()
        if not user_row:
            return {"error": "No user found"}
        user_id = str(user_row.id)

        col_res = await session.execute(text("SELECT card_id, quantity FROM user_collections WHERE user_id::text = :uid;"), {"uid": user_id})
        user_collection = {row.card_id: row.quantity for row in col_res.fetchall()}

        available_rares, available_mythics = 20, 8
        wc_res = await session.execute(text("SELECT rare, mythic FROM wildcard_inventories WHERE user_id::text = :uid LIMIT 1;"), {"uid": user_id})
        wc_row = wc_res.fetchone()
        if wc_row:
            available_rares = wc_row.rare or 20
            available_mythics = wc_row.mythic or 8

        decks_res = await session.execute(text("""
            SELECT d.id, d.name, d.format, da.final_score
            FROM decks d
            JOIN deck_analyses da ON da.deck_id = d.id;
        """))
        decks = decks_res.fetchall()

        recommendations = []
        for deck in decks:
            cards_res = await session.execute(text("""
                SELECT c.id, dc.quantity, cp.rarity
                FROM deck_cards dc
                JOIN cards c ON c.id = dc.card_id
                LEFT JOIN (
                    SELECT DISTINCT ON (card_id) card_id, rarity FROM card_prints
                ) cp ON cp.card_id = c.id
                WHERE dc.deck_id = :did;
            """), {"did": int(deck.id)})
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

            completion_score = (owned_count / total_required * 100.0) if total_required > 0 else 0.0
            rare_penalty = max(0, missing_rares - available_rares) * 5
            mythic_penalty = max(0, missing_mythics - available_mythics) * 8
            wildcard_efficiency = max(0.0, 100.0 - min(100.0, rare_penalty + mythic_penalty))

            rec_score = (deck.final_score or 50.0) * 0.50 + completion_score * 0.35 + wildcard_efficiency * 0.15

            recommendations.append({
                "deck": deck.name,
                "format": deck.format,
                "recommendation_score": round(rec_score, 2),
                "completion_score": round(completion_score, 1),
                "missing_rares": missing_rares,
                "missing_mythics": missing_mythics
            })

        recommendations.sort(key=lambda x: x["recommendation_score"], reverse=True)
        return {"user_id": user_id, "recommendations": recommendations}