from sqlalchemy import text
from database import AsyncSessionLocal

async def fetch_deck_upgrade(target_deck_name: str):
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

        deck_res = await session.execute(text("""
            SELECT id, name, format FROM decks WHERE LOWER(name) LIKE LOWER(:dname) LIMIT 1;
        """), {"dname": f"%{target_deck_name}%"})
        deck = deck_res.fetchone()

        if not deck:
            return {"error": f"Deck matching '{target_deck_name}' not found"}

        cards_res = await session.execute(text("""
            SELECT c.id, c.name, dc.quantity, cp.rarity
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            LEFT JOIN (
                SELECT DISTINCT ON (card_id) card_id, rarity FROM card_prints
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
                    "missing": deficit,
                    "rarity": "Mythic" if is_mythic else "Rare"
                })

        missing_cards.sort(key=lambda x: (x["rarity"] != "Mythic", -x["missing"]))
        craftable_now = (available_rares >= total_missing_rares) and (available_mythics >= total_missing_mythics)

        return {
            "deck": deck.name,
            "format": deck.format,
            "missing_rares": total_missing_rares,
            "missing_mythics": total_missing_mythics,
            "missing_cards": missing_cards,
            "craftable_now": craftable_now
        }