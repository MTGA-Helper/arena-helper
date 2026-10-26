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

# Slice 4 (TURBO surge, Oct 26, 2026): wildcard pricing buckets.
# A print's Scryfall rarity normalized to the wildcard that crafting a
# copy of the card at that printing costs. Mythic-tier treatments
# (special / masterpiece / bonus) craft with mythic wildcards; an
# unrecognized rarity prices as rare rather than silently costing 0.
_MYTHIC_TIER = ("mythic", "special", "masterpiece", "bonus")
_BUCKET_ORDER = {"common": 1, "uncommon": 2, "rare": 3, "mythic": 4}


def _craft_bucket(raw_rarity):
    r = (raw_rarity or "common").lower()
    if r in _MYTHIC_TIER:
        return "mythic"
    if r in _BUCKET_ORDER:
        return r
    return "rare"


def _deck_tally(deck_cards, user_collection):
    """Dedup a deck's card rows to one row per card and tally
    completion + the wildcard bill against the user's collection.

    Extracted in Slice 3 (TURBO surge, Oct 26, 2026) from
    get_deck_recommendations so the list endpoint and the deck-detail
    endpoint share ONE implementation of the completion / missing /
    wildcard math. deck_cards rows are (card_id, quantity, name,
    rarity, types) tuples — ONE ROW PER PRINT of each deck card (the
    CardPrint join fans out), the shape both endpoints query.

    Slice 4 (Oct 26, 2026) — the pricing fix. The pre-Slice-4 tally
    priced every deficit at the deck card's HIGHEST-rarity print and
    counted only rare + mythic wildcards. Both halves were wrong
    against the deck-choosing spec (build spec Step 5: costed at each
    card's CHEAPEST craftable printing; Step 4: basics free):
      - highest-print pricing overcharges multi-print cards —
        Fabled Passage has mythic prints, but crafting it costs a
        RARE wildcard (its cheapest printing);
      - uncommon / common deficits were listed in missing_cards but
        never tallied, so the bill understated the true total.
    The deduped display row still carries the highest-rarity print
    (what a deck list shows), but deficits are priced at the cheapest
    print, normalized by _craft_bucket, and tallied in all four
    buckets. Basic lands are free and unlimited on Arena: they count
    as owned, never appear in missing_cards, and never cost a
    wildcard. Acceptance: Matt's Jund Dino Madness against Billy's
    collection must total 41 wildcards = 10M / 25R / 5U / 1C
    (apps/api/test_slice4_wildcard_math.py; integration leg seeded
    by apps/desktop/test/jund_fixture.py).

    Returns (deduped_rows, total_required, total_owned, missing_cards,
    wildcard_cost, craft_rarity_by_card). wildcard_cost is
    {"common": n, "uncommon": n, "rare": n, "mythic": n};
    craft_rarity_by_card maps card_id -> its craft bucket.
    """
    total_required = 0
    total_owned = 0
    missing_cards = []
    wildcard_cost = {"common": 0, "uncommon": 0, "rare": 0, "mythic": 0}

    _rank = {"mythic": 4, "special": 4, "masterpiece": 4, "rare": 3, "uncommon": 2, "common": 1}
    _seen = {}
    _craft = {}
    _basic = set()
    for _cid, _qty, _name, _rar, _types in deck_cards:
        _r = (_rar or "common").lower()
        if _cid not in _seen or _rank.get(_r, 0) > _rank.get((_seen[_cid][2] or "common").lower(), 0):
            _seen[_cid] = (_qty, _name, _rar)
        _bucket = _craft_bucket(_r)
        if _cid not in _craft or _BUCKET_ORDER[_bucket] < _BUCKET_ORDER[_craft[_cid]]:
            _craft[_cid] = _bucket
        _t = _types or []
        if "Basic" in _t and "Land" in _t:
            _basic.add(_cid)

    deduped_deck_cards = [(_cid, _q, _n, _r) for _cid, (_q, _n, _r) in _seen.items()]

    for card_id, req_qty, card_name, rarity in deduped_deck_cards:
        total_required += req_qty
        if card_id in _basic:
            # Basics are free (see docstring): always fully owned.
            total_owned += req_qty
            continue
        owned_qty = user_collection.get(card_id, 0)
        effective_owned = min(owned_qty, req_qty)
        total_owned += effective_owned

        deficit = req_qty - effective_owned
        if deficit > 0:
            bucket = _craft[card_id]
            missing_cards.append({
                "name": card_name,
                "quantity": deficit,
                "rarity": bucket
            })
            wildcard_cost[bucket] += deficit

    return deduped_deck_cards, total_required, total_owned, missing_cards, wildcard_cost, _craft

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
                select(DeckCard.card_id, DeckCard.quantity, Card.name, CardPrint.rarity, Card.types)
                .join(Card, DeckCard.card_id == Card.id)
                .join(CardPrint, Card.id == CardPrint.card_id, isouter=True)
                .where(DeckCard.deck_id == deck.id)
            )
            deck_cards = dc_res.all()

            # Slice 3: the dedup + tally moved into _deck_tally
            # (above) so this endpoint and deck detail share one
            # implementation of the math. Slice 4: the tally prices
            # deficits at the cheapest print in all four rarities
            # (see _deck_tally) — Card.types rides along so it can
            # recognize free basic lands.
            _deduped, total_required, total_owned, missing_cards, wildcard_cost, _craft_map = _deck_tally(deck_cards, user_collection)

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
                "wildcard_cost": wildcard_cost,
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
        tally_rows = [(r.card_id, r.quantity, r.name, r.rarity, r.types) for r in rows]
        _deduped, total_required, total_owned, missing_cards, wildcard_cost, craft_map = _deck_tally(tally_rows, user_collection)

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
            # Slice 4: basic lands are free on Arena — never missing
            # (the tally above already counts them as owned) — and
            # each card carries its craft bucket so the deck report
            # can price the copies it is short at the cheapest
            # printing instead of the display print.
            _is_basic = "Basic" in (r.types or []) and "Land" in (r.types or [])
            cards.append({
                "name": r.name,
                "quantity": r.quantity,
                "owned": owned_qty,
                "missing": 0 if _is_basic else max(0, r.quantity - min(owned_qty, r.quantity)),
                "basic": _is_basic,
                "craft_rarity": craft_map.get(r.card_id),
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
            "wildcard_cost": wildcard_cost,
            "analysis": analysis
        }
