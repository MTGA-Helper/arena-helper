import asyncio
from sqlalchemy.future import select
from database import AsyncSessionLocal
from models import Card, CardTag

TAG_RULES = {
    "token_generator": [
        "create a token",
        "create two",
        "create a creature token"
    ],
    "card_draw": [
        "draw a card",
        "draw two cards"
    ],
    "removal": [
        "destroy target",
        "exile target",
        "deals damage to target creature"
    ],
    "counterspell": [
        "counter target spell"
    ],
    "boardwipe": [
        "destroy all creatures",
        "exile all creatures"
    ],
    "discard": [
        "target player discards"
    ],
    "lifegain": [
        "you gain"
    ],
    "ramp": [
        "search your library for a land",
        "add one mana"
    ],
    "artifact_synergy": [
        "artifact"
    ]
}

async def tag_cards_deterministic():
    print("[*] Running Deterministic Card Role Tagger (Priority #1)...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Card))
        cards = result.scalars().all()
        
        tagged_count = 0
        for card in cards:
            if not card.oracle_text:
                continue
                
            oracle = card.oracle_text.lower()

            for tag_name, patterns in TAG_RULES.items():
                if any(p in oracle for p in patterns):
                    # Check if tag already exists to respect unique constraint
                    existing_tag = await session.execute(
                        select(CardTag).where(CardTag.card_id == card.id, CardTag.tag == tag_name)
                    )
                    if not existing_tag.scalars().first():
                        new_tag = CardTag(
                            card_id=card.id,
                            tag=tag_name,
                            score=1.0,
                            source="oracle_parser"
                        )
                        session.add(new_tag)
                        tagged_count += 1

            if tagged_count > 0 and tagged_count % 1000 == 0:
                await session.commit()
                print(f"[+] Assigned {tagged_count} tags so far...")

        await session.commit()
        print(f"[+] Tagging complete! Successfully processed and assigned functional roles across card base.")

if __name__ == "__main__":
    asyncio.run(tag_cards_deterministic())
