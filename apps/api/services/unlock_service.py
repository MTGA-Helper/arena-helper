from sqlalchemy import text
from database import AsyncSessionLocal

async def fetch_unlocks():
    async with AsyncSessionLocal() as session:
        user_res = await session.execute(text("SELECT id FROM users LIMIT 1;"))
        user_row = user_res.fetchone()
        if not user_row:
            return {"error": "No user found"}
        user_id = str(user_row.id)

        col_res = await session.execute(text("SELECT card_id, quantity FROM user_collections WHERE user_id::text = :uid;"), {"uid": user_id})
        user_collection = {row.card_id: row.quantity for row in col_res.fetchall()}

        decks_res = await session.execute(text("""
            SELECT d.id, d.name, d.format, da.final_score
            FROM decks d
            JOIN deck_analyses da ON da.deck_id = d.id;
        """))
        decks = decks_res.fetchall()

        fully_buildable = []
        almost_buildable = []
        close_calls = []

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

            completion = (owned_count / total_required * 100.0) if total_required > 0 else 0.0
            total_missing_wc = missing_rares + missing_mythics

            deck_info = {
                "name": deck.name,
                "format": deck.format,
                "completion": round(completion, 1),
                "missing_rares": missing_rares,
                "missing_mythics": missing_mythics
            }

            if missing_rares == 0 and missing_mythics == 0:
                fully_buildable.append(deck_info)
            elif total_missing_wc <= 4:
                almost_buildable.append(deck_info)
            elif total_missing_wc <= 8:
                close_calls.append(deck_info)

        return {
            "fully_buildable": fully_buildable,
            "almost_buildable": almost_buildable,
            "close_calls": close_calls
        }