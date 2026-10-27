# -*- coding: utf-8 -*-
"""Arena Watcher sync (Slice 5, TURBO surge, Oct 26, 2026).

The desktop Arena Watcher tails the MTG Arena Player.log on the game
machine and posts the state it parses to this router. What the log
actually carries — verified against real Player.log files on
Oct 26, 2026, including a full recursive scan of two logs:

  - the player's deck library: the session dump's Decks /
    DeckSummaries maps, plus EventSetDeckV3 payloads, with card
    rows keyed by Arena grpId ({cardId, quantity} per board);
  - InventoryInfo snapshots: the four wildcard counts, gems, gold
    and vault progress.

What it does NOT carry: the owned-card collection. No Cards payload
exists anywhere in the current client's log (the scan found none, in
either log), so collection sync stays with the CSV upload
(POST /collection/upload) and nothing here pretends otherwise.
InventoryInfo.Changes deltas are likewise not reconstructed from:
both real logs carried empty Changes on every snapshot, and the
absolute counts on each snapshot are the state that matters.

Sync semantics mirror the collection upload's source-of-truth rule,
scoped per deck: each deck in the payload REPLACES the stored deck
with the same Arena id for the user, and the wildcard counts replace
the stored WildcardInventory row. grpIds resolve to engine cards
through CardPrint.arena_id (stored by the seed since Slice 5);
unresolved grpIds are stored raw and counted as unmatched, never
dropped — the same honesty the CSV importer applies to its rows.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.future import select

from apps.api.database import AsyncSessionLocal
from apps.api.models import (
    Card,
    CardPrint,
    User,
    UserCollection,
    UserDeck,
    UserDeckCard,
    WildcardInventory,
)

router = APIRouter(prefix="/watcher", tags=["Watcher"])

# The four boards a deck payload can carry, in payload order. The log
# names them MainDeck / Sideboard / CommandZone / Companions; the
# watcher parser maps them onto these keys.
BOARDS = ("main", "sideboard", "command", "companion")


# Dummy current user dependency for Phase 1 testing — the same stub
# shape as collection.py / recommendations.py (AU-1b tracks wiring
# real JWT verification into these routes).
async def get_current_user_id() -> UUID:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserCollection.user_id).limit(1))
        user_id = result.scalars().first()
        if not user_id:
            user_res = await session.execute(select(User).limit(1))
            user = user_res.scalars().first()
            if user:
                return user.id
            raise HTTPException(status_code=404, detail="No users found in database.")
        return user_id


class WatcherCardIn(BaseModel):
    grp_id: int
    quantity: int = 1
    board: str = "main"


class WatcherDeckIn(BaseModel):
    deck_id: str
    name: str
    format: Optional[str] = None
    cards: list[WatcherCardIn] = []


class WatcherInventoryIn(BaseModel):
    wildcards: Optional[dict] = None
    gems: Optional[int] = None
    gold: Optional[int] = None
    vault_progress: Optional[int] = None


class WatcherSyncIn(BaseModel):
    inventory: Optional[WatcherInventoryIn] = None
    decks: list[WatcherDeckIn] = []


def normalize_deck_cards(cards):
    """Merge duplicate (grp_id, board) rows, drop non-positive
    quantities, and clamp unknown boards to "main". Pure — the same
    defensive shaping the CSV importer applies to its rows, unit
    checked in apps/api/test_watcher_sync.py."""
    merged = {}
    for c in cards:
        board = c.board if c.board in BOARDS else "main"
        if c.quantity <= 0:
            continue
        key = (c.grp_id, board)
        merged[key] = merged.get(key, 0) + c.quantity
    return [
        {"grp_id": grp, "board": board, "quantity": qty}
        for (grp, board), qty in sorted(merged.items())
    ]


@router.post("/sync")
async def sync_watcher(body: WatcherSyncIn, user_id: UUID = Depends(get_current_user_id)):
    async with AsyncSessionLocal() as session:
        # Preload the grpId -> card map in one query, the way the
        # collection upload preloads its name/set maps: resolution is
        # O(1) per row and the corpus is only read, never per-row.
        print_res = await session.execute(
            select(CardPrint.arena_id, CardPrint.card_id).where(CardPrint.arena_id.is_not(None))
        )
        arena_map = {row[0]: row[1] for row in print_res.all()}

        decks_stored = 0
        card_rows = 0
        cards_matched = 0
        cards_unmatched = 0

        for deck in body.decks:
            rows = normalize_deck_cards(deck.cards)
            # Per-deck replacement (the upload's source-of-truth rule
            # at deck scope): the stored deck of this Arena id goes,
            # cards and all, and the payload's version lands. Card
            # rows are deleted explicitly first — a bulk delete does
            # not fire the ORM cascade, and no ON DELETE CASCADE is
            # declared on the foreign key.
            await session.execute(
                delete(UserDeckCard).where(
                    UserDeckCard.deck_id.in_(
                        select(UserDeck.id).where(
                            UserDeck.user_id == user_id,
                            UserDeck.arena_deck_id == deck.deck_id,
                        )
                    )
                )
            )
            await session.execute(
                delete(UserDeck).where(
                    UserDeck.user_id == user_id,
                    UserDeck.arena_deck_id == deck.deck_id,
                )
            )
            stored = UserDeck(
                user_id=user_id,
                arena_deck_id=deck.deck_id,
                name=deck.name,
                format=deck.format,
            )
            session.add(stored)
            await session.flush()
            for r in rows:
                card_id = arena_map.get(r["grp_id"])
                card_rows += 1
                if card_id is not None:
                    cards_matched += 1
                else:
                    cards_unmatched += 1
                session.add(
                    UserDeckCard(
                        deck_id=stored.id,
                        grp_id=r["grp_id"],
                        card_id=card_id,
                        quantity=r["quantity"],
                        board=r["board"],
                    )
                )
            decks_stored += 1

        wildcards_updated = False
        if body.inventory is not None and body.inventory.wildcards:
            wc = body.inventory.wildcards
            values = {
                k: int(wc.get(k) or 0)
                for k in ("common", "uncommon", "rare", "mythic")
            }
            wc_res = await session.execute(
                select(WildcardInventory).where(WildcardInventory.user_id == user_id)
            )
            row = wc_res.scalars().first()
            if row is None:
                session.add(WildcardInventory(user_id=user_id, **values))
            else:
                for k, v in values.items():
                    setattr(row, k, v)
            wildcards_updated = True

        await session.commit()

    return {
        "status": "success",
        "decks_received": len(body.decks),
        "decks_stored": decks_stored,
        "card_rows": card_rows,
        "cards_matched": cards_matched,
        "cards_unmatched": cards_unmatched,
        "wildcards_updated": wildcards_updated,
    }


@router.get("/decks")
async def get_watcher_decks(user_id: UUID = Depends(get_current_user_id)):
    """The stored watcher decks for the current user, with resolved
    card names where the corpus knows the grpId (name is null for
    unresolved rows — the grpId and quantity are the truth there)."""
    async with AsyncSessionLocal() as session:
        deck_res = await session.execute(
            select(UserDeck).where(UserDeck.user_id == user_id).order_by(UserDeck.name)
        )
        decks = deck_res.scalars().all()
        out = []
        for deck in decks:
            card_res = await session.execute(
                select(UserDeckCard, Card.name)
                .join(Card, UserDeckCard.card_id == Card.id, isouter=True)
                .where(UserDeckCard.deck_id == deck.id)
                .order_by(UserDeckCard.board, UserDeckCard.grp_id)
            )
            cards = [
                {
                    "grp_id": row.grp_id,
                    "name": name,
                    "quantity": row.quantity,
                    "board": row.board,
                }
                for row, name in card_res.all()
            ]
            out.append(
                {
                    "deck_id": deck.arena_deck_id,
                    "name": deck.name,
                    "format": deck.format,
                    "cards": cards,
                }
            )
        return out
