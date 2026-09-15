# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert
from database import AsyncSessionLocal
from models import Deck, DeckCard, Card

async def import_meta_decks():
    print("[+] Fetching meta deck snapshots...")
    
    sample_meta_decks = [
        {
            "name": "Boros Aggro",
            "archetype": "Aggro",
            "format": "standard",
            "tier": 1,
            "winrate": 58.5,
            "meta_share": 14.2,
            "source": "Sample Meta Feeds",
            "cards": [
                {"name": "Monastery Swiftspear", "quantity": 4},
                {"name": "Lightning Strike", "quantity": 4},
                {"name": "Slickshot Show-Off", "quantity": 4},
                {"name": "Play with Fire", "quantity": 4},
                {"name": "Manamorphose", "quantity": 4}
            ]
        },
        {
            "name": "Dimir Midrange",
            "archetype": "Midrange",
            "format": "standard",
            "tier": 1,
            "winrate": 56.8,
            "meta_share": 18.0,
            "source": "Sample Meta Feeds",
            "cards": [
                {"name": "Gix's Command", "quantity": 2},
                {"name": "Make Disappear", "quantity": 4},
                {"name": "Fatal Push", "quantity": 4},
                {"name": "Sheoldred, the Apocalypse", "quantity": 3}
            ]
        }
    ]

    async with AsyncSessionLocal() as session:
        for d_data in sample_meta_decks:
            res = await session.execute(select(Deck).where(Deck.name == d_data["name"], Deck.format == d_data["format"]))
            deck = res.scalars().first()

            now_utc = datetime.now(timezone.utc)

            if not deck:
                deck = Deck(
                    name=d_data["name"],
                    archetype=d_data["archetype"],
                    format=d_data["format"],
                    tier=d_data["tier"],
                    winrate=d_data["winrate"],
                    meta_share=d_data["meta_share"],
                    source=d_data["source"],
                    last_seen=now_utc
                )
                session.add(deck)
                await session.flush()
            else:
                deck.archetype = d_data["archetype"]
                deck.tier = d_data["tier"]
                deck.winrate = d_data["winrate"]
                deck.meta_share = d_data["meta_share"]
                deck.last_seen = now_utc

            deck_id = deck.id

            for c_item in d_data["cards"]:
                card_res = await session.execute(select(Card.id).where(Card.name.ilike(c_item["name"])))
                card_id = card_res.scalars().first()

                if card_id:
                    session.add(DeckCard(deck_id=deck_id, card_id=card_id, quantity=c_item["quantity"]))

        await session.commit()
        print("[+] Meta decks successfully imported and linked cleanly!")

if __name__ == "__main__":
    asyncio.run(import_meta_decks())
