import asyncio
from database import AsyncSessionLocal
from models import Deck, DeckCard, Card
from sqlalchemy.future import select

async def seed_test_deck():
    async with AsyncSessionLocal() as session:
        card_check = await session.execute(select(Card).limit(1))
        if not card_check.scalars().first():
            print("[-] Warning: No cards found in 'cards' table! Run your seeder first.")
            return

        deck = Deck(
            name="Boros Aggro Meta v1", 
            format="standard", 
            archetype="Aggro", 
            tier=1, 
            winrate=58.5, 
            meta_share=12.4
        )
        session.add(deck)
        await session.flush()

        cards_res = await session.execute(select(Card).limit(4))
        cards = cards_res.scalars().all()

        for card in cards:
            deck_card = DeckCard(deck_id=deck.id, card_id=card.id, quantity=4)
            session.add(deck_card)

        await session.commit()
        print(f"[+] Successfully seeded test deck: '{deck.name}' with {len(cards)} card types!")

if __name__ == "__main__":
    asyncio.run(seed_test_deck())
