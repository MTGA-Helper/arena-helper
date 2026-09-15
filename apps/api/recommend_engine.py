import asyncio
from sqlalchemy.future import select
from database import AsyncSessionLocal
from models import User, Card, CardTag, Deck, DeckCard, UserCollection, WildcardInventory

async def evaluate_decks_for_user(email: str):
    print(f"\n==================================================")
    print(f" RECOMMENDATION ENGINE: Analyzing Meta for '{email}'")
    print(f"==================================================")

    async with AsyncSessionLocal() as session:
        user_res = await session.execute(select(User).where(User.email == email))
        user = user_res.scalars().first()
        if not user:
            print(f"[-] User {email} not found.")
            return

        coll_res = await session.execute(
            select(UserCollection).where(UserCollection.user_id == user.id)
        )
        user_coll = {item.card_id: item.quantity for item in coll_res.scalars().all()}

        decks_res = await session.execute(select(Deck))
        decks = decks_res.scalars().all()

        if not decks:
            print("[-] No meta decks found in database. Run deck seeding first.")
            return

        recommendations = []

        for deck in decks:
            dc_res = await session.execute(
                select(DeckCard, Card).join(Card, DeckCard.card_id == Card.id).where(DeckCard.deck_id == deck.id)
            )
            deck_items = dc_res.all()

            total_cards = sum(dc.quantity for dc, _ in deck_items)
            if total_cards == 0:
                continue

            owned_count = 0
            synergy_points = 0

            for dc, card in deck_items:
                required = dc.quantity
                owned = user_coll.get(card.id, 0)
                owned_count += min(owned, required)

                tags_res = await session.execute(select(CardTag).where(CardTag.card_id == card.id))
                for tag_obj in tags_res.scalars().all():
                    synergy_points += tag_obj.score

            completion_score = (owned_count / total_cards) * 100
            meta_score = (deck.winrate / 60.0) * 100 if deck.winrate else 50.0
            synergy_score = min(100.0, synergy_points * 10)
            rotation_score = 90.0

            total_score = (
                completion_score * 0.40 +
                meta_score * 0.30 +
                synergy_score * 0.20 +
                rotation_score * 0.10
            )

            recommendations.append({
                "name": deck.name,
                "format": deck.format,
                "archetype": deck.archetype or "General",
                "winrate": deck.winrate or 50.0,
                "completion": round(completion_score, 1),
                "score": round(total_score, 1)
            })

        recommendations.sort(key=lambda x: x["score"], reverse=True)

        print("\n[+] Top Deck Recommendations:")
        for idx, rec in enumerate(recommendations[:5], 1):
            print(f"    #{idx} {rec['name']} ({rec['format'].capitalize()})")
            print(f"        - Overall Match Score: {rec['score']}/100")
            print(f"        - Collection Completion: {rec['completion']}%")
            print(f"        - Meta Winrate: {rec['winrate']}%")
            print(f"        - Archetype: {rec['archetype']}")

if __name__ == "__main__":
    asyncio.run(evaluate_decks_for_user("test@test.com"))
