# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.future import select
from uuid import UUID

from apps.api.database import AsyncSessionLocal
from apps.api.models import Deck, DeckCard, UserCollection, Card, CardPrint, DeckAnalysis
from services.next_action_service import get_next_action

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

async def get_current_user_id() -> UUID:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserCollection.user_id).limit(1))
        user_id = result.scalars().first()
        if not user_id:
            from apps.api.models import User
            user_res = await session.execute(select(User).limit(1))
            user = user_res.scalars().first()
            if user:
                return user.id
            raise HTTPException(status_code=404, detail="No users found in database.")
        return user_id

def _deck_tally(deck_cards, user_collection):
    """Dedup a deck's card rows to one row per card (highest-rarity
    print wins) and tally completion against the user's collection.

    Extracted in Slice 3 (TURBO surge, Oct 26, 2026) from
    get_deck_recommendations so the list endpoint and the deck-detail
    endpoint share ONE implementation of the completion / missing /
    wildcard math — behavior unchanged. deck_cards rows are
    (card_id, quantity, name, rarity) tuples, the shape both endpoints
    query. Returns (deduped_rows, total_required, total_owned,
    missing_cards, rare_wc, mythic_wc).
    """
    total_required = 0
    total_owned = 0
    missing_cards = []
    rare_wc = 0
    mythic_wc = 0

    _rank = {"mythic": 4, "special": 4, "masterpiece": 4, "rare": 3, "uncommon": 2, "common": 1}
    _seen = {}
    for _cid, _qty, _name, _rar in deck_cards:
        _r = (_rar or "common").lower()
        if _cid not in _seen or _rank.get(_r, 0) > _rank.get((_seen[_cid][2] or "common").lower(), 0):
            _seen[_cid] = (_qty, _name, _rar)

    deduped_deck_cards = [(_cid, _q, _n, _r) for _cid, (_q, _n, _r) in _seen.items()]

    for card_id, req_qty, card_name, rarity in deduped_deck_cards:
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

    return deduped_deck_cards, total_required, total_owned, missing_cards, rare_wc, mythic_wc

@router.get("/decks")
async def get_deck_recommendations(user_id: UUID = Depends(get_current_user_id)):
    async with AsyncSessionLocal() as session:
        coll_res = await session.execute(
            select(UserCollection.card_id, UserCollection.quantity)
            .where(UserCollection.user_id == user_id)
        )
        user_collection = {row.card_id: row.quantity for row in coll_res.all()}

        decks_res = await session.execute(select(Deck))
        decks = decks_res.scalars().all()

        recommendations = []

        for deck in decks:
            dc_res = await session.execute(
                select(DeckCard.card_id, DeckCard.quantity, Card.name, CardPrint.rarity)
                .join(Card, DeckCard.card_id == Card.id)
                .join(CardPrint, Card.id == CardPrint.card_id, isouter=True)
                .where(DeckCard.deck_id == deck.id)
            )
            deck_cards = dc_res.all()

            # Slice 3: the dedup + tally moved into _deck_tally
            # (above) so this endpoint and deck detail share one
            # implementation of the math — behavior unchanged.
            _deduped, total_required, total_owned, missing_cards, rare_wc, mythic_wc = _deck_tally(deck_cards, user_collection)

            completion_percent = (total_owned / total_required * 100.0) if total_required > 0 else 0.0
            base_winrate = deck.winrate or 50.0
            rank_score = (completion_percent * 0.70) + (base_winrate * 0.30)

            recommendations.append({
                "deck_id": deck.id,
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

        recommendations.sort(key=lambda x: x["rank_score"], reverse=True)
        return recommendations

@router.get("/next-action")
async def next_action_endpoint():
    return await get_next_action()

@router.get("/decks/{deck_id}")
async def get_deck_detail(deck_id: int, user_id: UUID = Depends(get_current_user_id)):
    """Slice 3 (TURBO surge, Oct 26, 2026): one deck in full — its card
    list (with the type line + subtypes the seed now stores), per-card
    owned/missing against the signed-in collection, and the deck's
    stored analysis from deck_analyses, served exactly as
    deck_analysis.py computed it. The metric definitions are the
    engine's current ones — the "synergy score" is tag density (KB
    gap #4); whether that metric changes is a co-captain decision, so
    this endpoint renders the stored numbers faithfully.
    """
    async with AsyncSessionLocal() as session:
        deck_res = await session.execute(select(Deck).where(Deck.id == deck_id))
        deck = deck_res.scalars().first()
        if not deck:
            raise HTTPException(status_code=404, detail="Deck not found.")

        coll_res = await session.execute(
            select(UserCollection.card_id, UserCollection.quantity)
            .where(UserCollection.user_id == user_id)
        )
        user_collection = {row.card_id: row.quantity for row in coll_res.all()}

        dc_res = await session.execute(
            select(DeckCard.card_id, DeckCard.quantity, Card.name, CardPrint.rarity,
                   Card.mana_value, Card.colors, Card.types, Card.subtypes, Card.type_line)
            .join(Card, DeckCard.card_id == Card.id)
            .join(CardPrint, Card.id == CardPrint.card_id, isouter=True)
            .where(DeckCard.deck_id == deck.id)
        )
        rows = dc_res.all()

        # Completion / missing / wildcard math comes from the same
        # _deck_tally the list endpoint uses (fed the 4-tuples it
        # understands), so detail can never drift from the list.
        tally_rows = [(r.card_id, r.quantity, r.name, r.rarity) for r in rows]
        _deduped, total_required, total_owned, missing_cards, rare_wc, mythic_wc = _deck_tally(tally_rows, user_collection)

        # Display rows keep the full card fields of the winning print's
        # row — the same highest-rarity-wins rule _deck_tally applies.
        _rank = {"mythic": 4, "special": 4, "masterpiece": 4, "rare": 3, "uncommon": 2, "common": 1}
        best = {}
        for r in rows:
            cur = best.get(r.card_id)
            if cur is None or _rank.get((r.rarity or "common").lower(), 0) > _rank.get((cur.rarity or "common").lower(), 0):
                best[r.card_id] = r

        cards = []
        for r in best.values():
            owned_qty = user_collection.get(r.card_id, 0)
            cards.append({
                "name": r.name,
                "quantity": r.quantity,
                "owned": owned_qty,
                "missing": max(0, r.quantity - min(owned_qty, r.quantity)),
                "rarity": (r.rarity or "common").lower(),
                "mana_value": r.mana_value,
                "colors": r.colors or [],
                "types": r.types or [],
                "subtypes": r.subtypes or [],
                "type_line": r.type_line,
            })
        # Curve order: mana value, then name (lands sit at 0).
        cards.sort(key=lambda c: (c["mana_value"] if c["mana_value"] is not None else 0.0, c["name"]))

        analysis_res = await session.execute(
            select(DeckAnalysis)
            .where(DeckAnalysis.deck_id == deck.id)
            .order_by(DeckAnalysis.id.desc())
            .limit(1)
        )
        analysis_row = analysis_res.scalars().first()
        analysis = None
        if analysis_row:
            analysis = {
                "synergy_score": analysis_row.synergy_score,
                "consistency_score": analysis_row.consistency_score,
                "mana_score": analysis_row.mana_score,
                "meta_score": analysis_row.meta_score,
                "final_score": analysis_row.final_score,
            }

        completion_percent = (total_owned / total_required * 100.0) if total_required > 0 else 0.0

        return {
            "deck_id": deck.id,
            "deck_name": deck.name,
            "archetype": deck.archetype,
            "format": deck.format,
            "tier": deck.tier,
            "winrate": deck.winrate if deck.winrate is not None else 50.0,
            "meta_share": deck.meta_share,
            "completion_percent": round(completion_percent, 1),
            "cards_owned": total_owned,
            "cards_required": total_required,
            "cards": cards,
            "missing_cards": missing_cards,
            "wildcard_cost": {
                "rare": rare_wc,
                "mythic": mythic_wc
            },
            "analysis": analysis
        }
