# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.future import select
from sqlalchemy import join
from uuid import UUID

from database import AsyncSessionLocal
from models import Deck, DeckCard, UserCollection, Card, CardPrint

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

async def get_current_user_id() -> UUID:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserCollection.user_id).limit(1))
        user_id = result.scalars().first()
        if not user_id:
            from models import User
            user_res = await session.execute(select(User).limit(1))
            user = user_res.scalars().first()
            if user:
                return user.id
            raise HTTPException(status_code=404, detail="No users found in database.")
        return user_id

@router.get("/decks")
async def get_deck_recommendations(user_id: UUID = Depends(get_current_user_id)):
    async with AsyncSessionLocal() as session:
        # 1. Fetch user collection map: {card_id: quantity}
        coll_res = await session.execute(
            select(UserCollection.card_id, UserCollection.quantity)
            .where(UserCollection.user_id == user_id)
        )
        user_collection = {row.card_id: row.quantity for row in coll_res.all()}

        # 2. Fetch all decks and their required cards
        decks_res = await session.execute(select(Deck))
        decks = decks_res.scalars().all()

        recommendations = []

        for deck in decks:
            # Fetch cards associated with this deck, joining with Card and CardPrint for rarity
            dc_res = await session.execute(
                select(DeckCard.card_id, DeckCard.quantity, Card.name, CardPrint.rarity)
                .join(Card, DeckCard.card_id == Card.id)
                .join(CardPrint, Card.id == CardPrint.card_id, isouter=True)
                .where(DeckCard.deck_id == deck.id)
            )
            deck_cards = dc_res.all()

            total_required = 0
            total_owned = 0
            missing_cards = []
            rare_wc = 0
            mythic_wc = 0

            for card_id, req_qty, card_name, rarity in deck_cards:
                total_required += req_qty
                owned_qty = user_collection.get(card_id, 0)
                effective_owned = min(owned_qty, req_qty)
                total_owned += effective_owned

                deficit = req_qty - effective_owned
                if deficit > 0:
                    card_rarity = (rarity or "common").lower()
                    missing_cards.append({
                        "name": card_name,
                        "quantity": deficit,
                        "rarity": card_rarity
                    })

                    if card_rarity == "rare":
                        rare_wc += deficit
                    elif card_rarity == "mythic":
                        mythic_wc += deficit

            completion_percent = (total_owned / total_required * 100.0) if total_required > 0 else 0.0
            
            # Ranking formula V1: (completion_percent * 0.70) + (winrate * 0.30)
            base_winrate = deck.winrate or 50.0
            rank_score = (completion_percent * 0.70) + (base_winrate * 0.30)

            recommendations.append({
                "deck_name": deck.name,
                "archetype": deck.archetype,
                "format": deck.format,
                "tier": deck.tier,
                "winrate": base_winrate,
                "completion_percent": round(completion_percent, 1),
                "cards_owned": total_owned,
                "cards_required": total_required,
                "missing_cards": missing_cards,
                "wildcard_cost": {
                    "rare": rare_wc,
                    "mythic": mythic_wc
                },
                "rank_score": rank_score
            })

        # Sort recommendations by rank score descending
        recommendations.sort(key=lambda x: x["rank_score"], reverse=True)

        return recommendations
