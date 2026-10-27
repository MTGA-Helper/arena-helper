import asyncio
from sqlalchemy import text
from apps.api.database import AsyncSessionLocal

# Slice 4 (TURBO surge, Oct 26, 2026): craft pricing buckets — the
# same normalization recommendations._craft_bucket applies. A print
# rarity becomes the wildcard that crafting at that printing costs;
# mythic-tier treatments (special / masterpiece / bonus) price as
# mythic, and an unrecognized rarity prices as rare rather than 0.
_MYTHIC_TIER = ("mythic", "special", "masterpiece", "bonus")
_BUCKET_ORDER = {"common": 1, "uncommon": 2, "rare": 3, "mythic": 4}


def _craft_bucket(raw_rarity):
    r = (raw_rarity or "rare").lower()
    if r in _MYTHIC_TIER:
        return "mythic"
    if r in _BUCKET_ORDER:
        return r
    return "rare"


def build_craft_priorities(decks, user_collection):
    """Pure aggregation behind the craft priority report (extracted
    in Slice 4 so the math is unit-testable without a database —
    apps/api/test_slice4_wildcard_math.py).

    decks: [{"deck_name", "deck_score", "cards": [{"card_id",
    "card_name", "quantity", "rarity"}]}] where each card's rarity
    is its CHEAPEST print's rarity (the report query orders the
    prints so), and "is_basic" marks basic lands, which are free
    on Arena and never craft candidates. user_collection:
    {card_id: copies owned}.

    Slice 4 fix (KB gap #12): the pre-fix report summed a card's
    deficit over EVERY deck ("total_deficit") and charged that sum
    as the craft cost — but one crafted playset serves all decks at
    once, so the same copies were charged once per deck. Cost is
    now the copies to craft ONCE: the largest single-deck deficit.
    The pre-fix rarity label also collapsed everything non-mythic
    to "Rare"; the bucket is now the card's real craft bucket in
    all four rarities. The ranking formula is unchanged — only the
    cost it divides by (and the price label) is honest now.
    """
    card_opportunities = {}

    for deck in decks:
        for dc in deck["cards"]:
            # Basic lands are free and unlimited on Arena — never a
            # craft candidate. (The pre-fix report had no such
            # exclusion and ranked "craft a Forest" #1 whenever the
            # collection held no basics; the Slice 4 Jund fixture
            # run exposed it the day the gap #12 fix landed.)
            if dc.get("is_basic"):
                continue
            user_owned = user_collection.get(dc["card_id"], 0)
            needed = dc["quantity"]
            if user_owned >= needed:
                continue
            deficit = needed - user_owned
            entry = card_opportunities.setdefault(dc["card_id"], {
                "card_name": dc["card_name"],
                "rarity": _craft_bucket(dc["rarity"]),
                "unlocks_decks": [],
                "cost": 0,
            })
            entry["unlocks_decks"].append({
                "deck_name": deck["deck_name"],
                "deficit": deficit,
                "deck_score": deck["deck_score"],
            })
            # Copies to craft once = the largest single-deck deficit.
            # (Pre-fix: cost += deficit, summed across decks.)
            if deficit > entry["cost"]:
                entry["cost"] = deficit

    ranked_crafts = []
    for cid, info in card_opportunities.items():
        deck_count = len(info["unlocks_decks"])
        cumulative_deck_score = sum(d["deck_score"] for d in info["unlocks_decks"])
        cost = info["cost"]

        # Craft Score = (Sum of Meta Scores of decks it helps complete)
        # * (Number of decks unlocked) / (Cost) — the pre-fix formula,
        # unchanged; Slice 4 fixed the cost it divides by.
        craft_score = (cumulative_deck_score * deck_count) / max(1, cost * 0.5)

        ranked_crafts.append({
            "card_name": info["card_name"],
            "rarity": info["rarity"].capitalize(),
            "unlocks": info["unlocks_decks"],
            "cost": cost,
            "score": craft_score
        })

    ranked_crafts.sort(key=lambda x: x["score"], reverse=True)
    return ranked_crafts


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

            # Slice 4: gather each deck's cards with the rarity of
            # the card's CHEAPEST print. DISTINCT ON takes the first
            # row per card under the ORDER BY, so prints are ordered
            # by craft bucket (common first) — the pre-fix subquery
            # had no ORDER BY and priced off an arbitrary print.
            decks_payload = []
            for deck in decks:
                cards_res = await session.execute(text("""
                    SELECT
                        c.id,
                        c.name,
                        dc.quantity,
                        cp.rarity,
                        c.types
                    FROM deck_cards dc
                    JOIN cards c ON c.id = dc.card_id
                    LEFT JOIN (
                        SELECT DISTINCT ON (card_id) card_id, rarity
                        FROM card_prints
                        ORDER BY card_id, CASE lower(rarity)
                            WHEN 'common' THEN 1
                            WHEN 'uncommon' THEN 2
                            WHEN 'rare' THEN 3
                            ELSE 4 END, id
                    ) cp ON cp.card_id = c.id
                    WHERE dc.deck_id = :did;
                """), {"did": int(deck.id)})
                deck_cards = cards_res.fetchall()
                decks_payload.append({
                    "deck_name": deck.name,
                    "deck_score": deck.final_score or 50.0,
                    "cards": [
                        {"card_id": dc.id, "card_name": dc.name,
                         "quantity": dc.quantity, "rarity": dc.rarity,
                         "is_basic": "Basic" in (dc.types or [])
                                     and "Land" in (dc.types or [])}
                        for dc in deck_cards
                    ],
                })

            # Scoring & ranking live in build_craft_priorities (pure,
            # unit-tested) — Slice 4 extraction, see its docstring.
            ranked_crafts = build_craft_priorities(decks_payload, user_collection)

            print("\n" + "="*50)
            print("--- CRAFT PRIORITY REPORT ---")
            print("="*50)

            for i, craft in enumerate(ranked_crafts[:5], 1):
                print(f"\n#{i} {craft['card_name']} ({craft['rarity']})")
                print(f"Unlocks / Helps Complete:")
                for u in craft["unlocks"]:
                    print(f"  • {u['deck_name']} (Needed: {u['deficit']}x)")
                print(f"Cost:")
                print(f"  • {craft['cost']} {craft['rarity']} (craft once — serves every deck above)")

            print("="*50 + "\n")

        except Exception as e:
            await session.rollback()
            print(f"[!] Error generating craft priority report: {e}")

if __name__ == "__main__":
    asyncio.run(generate_craft_priority_report())
