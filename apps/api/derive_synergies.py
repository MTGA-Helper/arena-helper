# -*- coding: utf-8 -*-
"""
Populate card_synergies from derived co-occurrence/tag evidence.

Reads decks, deck_cards, and card_tags, runs the pure derivation in
synergy_derivation.py, and (only with --write) stores the results in the
card_synergies table.

Safety:
- Default mode is a dry run: it prints what would be written and commits
  nothing.
- A write replaces ONLY rows whose synergy_type starts with "derived:"
  (the namespace this pipeline owns). Hand-authored synergy rows are
  never deleted or modified.
- Pairs come exclusively from real deck rosters; if no two cards share a
  deck, the honest result is zero rows.

Usage:
    python -m apps.api.derive_synergies            # dry run
    python -m apps.api.derive_synergies --write    # persist derived rows
"""
import argparse
import asyncio
from collections import defaultdict

from sqlalchemy import delete, func, select

from apps.api.database import AsyncSessionLocal
from apps.api.models import CardSynergy, CardTag, Deck, DeckCard
from apps.api.synergy_derivation import (
    DeckRoster,
    DerivedSynergy,
    derive_synergies,
)

DERIVED_PREFIX = "derived:"


def build_synergy_row(derived: DerivedSynergy) -> CardSynergy:
    """Map one derived pair onto a CardSynergy ORM row (not yet persisted)."""
    return CardSynergy(
        card_a_id=derived.card_a_id,
        card_b_id=derived.card_b_id,
        synergy_type=derived.synergy_type,
        score=derived.score,
        confidence=derived.confidence,
        reason=derived.reason,
        format=derived.format,
    )


async def load_inputs(session):
    """Load deck rosters and card tag weights from the database."""
    deck_rows = (await session.execute(select(Deck.id, Deck.format))).all()
    formats = {deck_id: fmt for deck_id, fmt in deck_rows}

    cards_by_deck = defaultdict(list)
    dc_rows = (
        await session.execute(select(DeckCard.deck_id, DeckCard.card_id))
    ).all()
    for deck_id, card_id in dc_rows:
        if deck_id in formats:
            cards_by_deck[deck_id].append(card_id)

    rosters = [
        DeckRoster(deck_id=deck_id, format=formats[deck_id], card_ids=cards)
        for deck_id, cards in cards_by_deck.items()
    ]

    card_tags = defaultdict(dict)
    tag_rows = (
        await session.execute(select(CardTag.card_id, CardTag.tag, CardTag.score))
    ).all()
    for card_id, tag, score in tag_rows:
        card_tags[card_id][tag] = score if score is not None else 1.0

    return rosters, card_tags


async def derive_card_synergies(write: bool = False, min_co_decks: int = 1):
    print("[*] Starting derived synergy population (Phase 2 slice)...")
    async with AsyncSessionLocal() as session:
        try:
            rosters, card_tags = await load_inputs(session)
            total_cards = sum(len(set(r.card_ids)) for r in rosters)
            print(
                f"[*] Loaded {len(rosters)} deck rosters "
                f"({total_cards} distinct card slots) and tags for "
                f"{len(card_tags)} cards."
            )

            derived = derive_synergies(
                rosters, card_tags, min_co_decks=min_co_decks
            )
            print(f"[*] Derived {len(derived)} synergy candidate pair(s).")
            for row in derived[:20]:
                print(
                    f"    pair {row.card_a_id}-{row.card_b_id} [{row.format}] "
                    f"score={row.score} confidence={row.confidence} "
                    f"({row.synergy_type})"
                )
            if len(derived) > 20:
                print(f"    ... and {len(derived) - 20} more")

            existing = await session.scalar(
                select(func.count())
                .select_from(CardSynergy)
                .where(CardSynergy.synergy_type.startswith(DERIVED_PREFIX))
            )
            print(f"[*] Existing derived rows in card_synergies: {existing}")

            if not write:
                print("[+] Dry run only — nothing written. Re-run with --write to persist.")
                return derived

            await session.execute(
                delete(CardSynergy).where(
                    CardSynergy.synergy_type.startswith(DERIVED_PREFIX)
                )
            )
            session.add_all([build_synergy_row(d) for d in derived])
            await session.commit()
            print(
                f"[+] Wrote {len(derived)} derived rows to card_synergies "
                f"(replaced {existing} previous derived rows)."
            )
            return derived

        except Exception as e:
            await session.rollback()
            print(f"[!] Error deriving synergies: {e}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="persist derived rows (default: dry run, writes nothing)",
    )
    parser.add_argument(
        "--min-co-decks",
        type=int,
        default=1,
        help="minimum decks a pair must co-occur in (default: 1)",
    )
    args = parser.parse_args()
    asyncio.run(
        derive_card_synergies(write=args.write, min_co_decks=args.min_co_decks)
    )
