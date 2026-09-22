import asyncio
import sys
from sqlalchemy.future import select
from database import AsyncSessionLocal
from models import User, Card, CardPrint, Deck, DeckCard, UserCollection, WildcardInventory

async def run_alpha_snap(email: str, deck_name: str):
    print(f"\n==================================================")
    print(f" ALPHA-SNAP ENGINE: Evaluating '{deck_name}'")
    print(f"==================================================")

    async with AsyncSessionLocal() as session:
        # 1. Fetch User & Wildcards
        user_res = await session.execute(select(User).where(User.email == email))
        user = user_res.scalars().first()
        if not user:
            print(f"[-] Error: User '{email}' not found in database.")
            return

        wc_res = await session.execute(select(WildcardInventory).where(WildcardInventory.user_id == user.id))
        wildcards = wc_res.scalars().first()
        
        if not wildcards:
            # Auto-create inventory if missing so testing isn't blocked
            wildcards = WildcardInventory(user_id=user.id, common=99, uncommon=99, rare=20, mythic=10)
            session.add(wildcards)
            await session.commit()

        wc_rare = wildcards.rare
        wc_mythic = wildcards.mythic

        # 2. Fetch Deck
        deck_res = await session.execute(select(Deck).where(Deck.name.ilike(f"%{deck_name}%")))
        deck = deck_res.scalars().first()
        if not deck:
            print(f"[-] Error: Deck '{deck_name}' not found in database.")
            return

        # 3. Fetch Deck Cards with Card and CardPrint details
        deck_cards_res = await session.execute(
            select(DeckCard, Card, CardPrint)
            .join(Card, DeckCard.card_id == Card.id)
            .outerjoin(CardPrint, Card.id == CardPrint.card_id)
            .where(DeckCard.deck_id == deck.id)
        )
        deck_items = deck_cards_res.all()

        # 4. Fetch User Collection
        coll_res = await session.execute(
            select(UserCollection, Card)
            .join(Card, UserCollection.card_id == Card.id)
            .where(UserCollection.user_id == user.id)
        )
        user_coll_map = {item.Card.id: item.UserCollection.quantity for item in coll_res.all()}

        total_deck_cards = sum(deck_card.quantity for deck_card, _, _ in deck_items)
        owned_card_count = 0
        missing_rares = 0
        missing_mythics = 0
        missing_breakdown = []

        for deck_card, card, card_print in deck_items:
            required_qty = deck_card.quantity
            owned_qty = user_coll_map.get(card.id, 0)

            effective_owned = min(owned_qty, required_qty)
            owned_card_count += effective_owned

            rarity = card_print.rarity if card_print else "common"
            deficit = required_qty - effective_owned
            if deficit > 0:
                missing_breakdown.append((card.name, deficit, rarity))
                if rarity.lower() == 'rare':
                    missing_rares += deficit
                elif rarity.lower() == 'mythic':
                    missing_mythics += deficit

        completion_pct = round((owned_card_count / total_deck_cards) * 100, 1) if total_deck_cards > 0 else 0.0

        print(f"\n[+] Target Deck: {deck.name} ({deck.format})")
        print(f"[+] Collection Completion: {completion_pct}% ({owned_card_count}/{total_deck_cards} cards owned)")
        print(f"\n[+] Wildcard Economics:")
        print(f"    - Rare Wildcards Needed: {missing_rares} (You have: {wc_rare})")
        print(f"    - Mythic Wildcards Needed: {missing_mythics} (You have: {wc_mythic})")
        
        if missing_breakdown:
            print(f"\n[+] Missing Cards Breakdown:")
            for name, def_qty, rar in missing_breakdown:
                print(f"    - {def_qty}x {name} ({rar.capitalize()})")

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "test@test.com"
    deck_name = sys.argv[2] if len(sys.argv) > 2 else "Boros Aggro"
    asyncio.run(run_alpha_snap(email, deck_name))
