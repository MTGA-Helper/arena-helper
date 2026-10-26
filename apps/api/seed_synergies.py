#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seed the card_synergies table from the KB §7 signal library.

STRETCH — Slice 4 (TURBO surge, Oct 26, 2026). The card_synergies
table has existed since the schema was first written and has never
held a single row: deck_analysis computes "synergy" as tag density
(KB gap #4) and nothing reads pair data. This script wires the
table as SEED DATA ONLY — producer -> payoff pairs derived from the
oracle-text signal shapes catalogued in the MTG logic knowledge
base, §7 (files/mtg-logic-knowledge-base.md):

  * a PRODUCER creates an event (gains life, sacrifices, creates a
    token, casts a spell, stocks the yard, places counters, ramps,
    draws);
  * a PAYOFF listens for that event ("whenever you gain life", ...).
  A pair (producer, payoff) in the same event class is a candidate
  synergy, stored with synergy_type "<class>_engine".

The score/confidence written here are SEED PRIORS (0.6 / 0.5),
labeled as such in every reason string — they are not a measured
synergy metric. Whether pair data should replace or refine the
tag-density metric is the co-captain's open decision (KB gap #4);
this script deliberately does not touch deck_analysis.

Pool discipline (small-tables rule): pairs are generated only
among cards that appear in at least one deck in the target
database (deck_cards) — synergy is consumed per deck, and a
corpus-wide cross product would be ~10^5-10^6 rows of noise. The
run summary also prints the corpus-wide class sizes as information.

Idempotent: inserts use ON CONFLICT DO NOTHING against the
(card_a_id, card_b_id) unique constraint, so re-runs add nothing.

Run (from the repo root, API venv):

    SYNC_DATABASE_URL=<redacted>
        python3 apps/api/seed_synergies.py
"""
import os
import re
import sys

# --- KB §7 signal shapes (case-insensitive; [^\n]* where §7's ".*"
# --- must not run across oracle-text lines) -----------------------
_PATTERNS = {
    # class: (producer regexes, payoff regexes, producer keywords, payoff keywords)
    "lifegain": (
        [r"gains? (you )?[0-9x]+ life", r"gains? lifelink"],
        [r"whenever you gain life"],
        {"lifelink"},
        set(),
    ),
    "sacrifice": (
        [r"sacrifice (a|an|this|another) "],
        [r"whenever (a player|you|a creature) (sacrifices|dies)",
         r"whenever another creature dies"],
        set(),
        set(),
    ),
    "tokens": (
        [r"create (a |an |[0-9]+ |x )?[^\n]*token"],
        [r"(creatures|tokens) you control get \+"],
        set(),
        set(),
    ),
    "spellcast": (
        [],  # producers are the spells themselves (Instant/Sorcery types)
        [r"whenever you cast (a |an )?(instant|sorcery|noncreature)",
         r"\bmagecraft\b"],
        set(),
        {"prowess"},
    ),
    "graveyard": (
        [r"\bmill\b", r"discard a card", r"\bsurveil\b"],
        [r"cast [^\n]* from your graveyard",
         r"return [^\n]* from your graveyard to (the battlefield|your hand)"],
        set(),
        {"flashback", "escape", "unearth"},
    ),
    "counters": (
        [r"put [^\n]*\+1/\+1 counter", r"\bproliferate\b"],
        [r"that many plus (one|two) [^\n]* instead"],
        set(),
        set(),
    ),
    "landfall": (
        [r"search your library for a [^\n]* land",
         r"put a land [^\n]* onto the battlefield",
         r"create a [^\n]*treasure token",
         r"add one mana"],
        [r"\blandfall\b", r"whenever a land [^\n]* enters"],
        set(),
        set(),
    ),
    "draw": (
        [r"draw (a|one|two|three|four|x|[0-9]+) cards?"],
        [r"whenever you draw a card"],
        set(),
        set(),
    ),
}

_COMPILED = {
    cls: ([re.compile(p, re.IGNORECASE) for p in prod],
          [re.compile(p, re.IGNORECASE) for p in pay])
    for cls, (prod, pay, _pk, _yk) in _PATTERNS.items()
}

SEED_SCORE = 0.6
SEED_CONFIDENCE = 0.5


def classify_card(oracle_text, keywords, types):
    """Return (producer_classes, payoff_classes) for one card, per
    the KB §7 shapes. Pure function — unit-tested in
    test_seed_synergies.py."""
    text = oracle_text or ""
    kws = {str(k).strip().lower() for k in (keywords or [])}
    type_set = {str(t).strip() for t in (types or [])}
    producers, payoffs = set(), set()
    for cls, (prod_res, pay_res) in _COMPILED.items():
        _p, _y, prod_kws, pay_kws = _PATTERNS[cls]
        if any(r.search(text) for r in prod_res) or (kws & prod_kws):
            producers.add(cls)
        if any(r.search(text) for r in pay_res) or (kws & pay_kws):
            payoffs.add(cls)
    # §7 spellcast: the spells themselves are the event producers.
    if type_set & {"Instant", "Sorcery"}:
        producers.add("spellcast")
    return producers, payoffs


def build_pairs(cards):
    """cards: iterable of dicts with id/name/oracle_text/keywords/types.
    Returns a list of (card_a_id, card_b_id, synergy_type, reason)
    with card_a the producer and card_b the payoff, a != b."""
    by_class_prod, by_class_pay = {}, {}
    names = {}
    for c in cards:
        names[c["id"]] = c["name"]
        prod, pay = classify_card(c.get("oracle_text"), c.get("keywords"),
                                  c.get("types"))
        for cls in prod:
            by_class_prod.setdefault(cls, []).append(c["id"])
        for cls in pay:
            by_class_pay.setdefault(cls, []).append(c["id"])
    pairs = []
    for cls, prod_ids in by_class_prod.items():
        for a in prod_ids:
            for b in by_class_pay.get(cls, []):
                if a == b:
                    continue
                pairs.append((
                    a, b, f"{cls}_engine",
                    f"KB S7 seed pair ({cls}): {names[a]} produces the "
                    f"event; {names[b]} pays off on it. Seed prior, "
                    f"not a measured synergy (KB gap #4).",
                ))
    return pairs


def main():
    sync_url = os.environ.get("SYNC_DATABASE_URL", "")
    if not sync_url:
        print("ERROR: SYNC_DATABASE_URL is not set (see module docstring).")
        return 1
    from sqlalchemy import create_engine, text as sql_text
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        pool = conn.execute(sql_text(
            "SELECT DISTINCT c.id, c.name, c.oracle_text, c.keywords, c.types "
            "FROM cards c JOIN deck_cards dc ON dc.card_id = c.id"
        )).mappings().all()
        corpus = conn.execute(sql_text(
            "SELECT COUNT(*) FROM cards")).scalar()
    print(f"deck pool: {len(pool)} unique cards (corpus: {corpus})")
    pairs = build_pairs([dict(r) for r in pool])
    by_type = {}
    for _a, _b, t, _r in pairs:
        by_type[t] = by_type.get(t, 0) + 1
    for t in sorted(by_type):
        print(f"  {t}: {by_type[t]} pairs")
    print(f"total pairs: {len(pairs)}")
    if not pairs:
        print("nothing to insert.")
        return 0
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from apps.api.models import CardSynergy
    rows = [{"card_a_id": a, "card_b_id": b, "synergy_type": t,
             "score": SEED_SCORE, "confidence": SEED_CONFIDENCE,
             "reason": r, "format": "all"}
            for a, b, t, r in pairs]
    with engine.begin() as conn:
        stmt = pg_insert(CardSynergy).values(rows).on_conflict_do_nothing(
            constraint="uq_card_synergy")
        result = conn.execute(stmt)
        print(f"inserted: {result.rowcount} new rows "
              f"({len(rows) - result.rowcount} already present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
