#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 5 watcher fixture — extends the Slice 2 collection fixture
with the grpId corpus the watcher sync resolves against.

    SYNC_DATABASE_URL=postgresql://arena@/arena_fixture?host=/tmp&port=54329 \\
      python3 test/watcher_fixture.py

Run AFTER test/collection_fixture.py (this script refuses to run
without its fixture user) and run the smoke's watcher legs LAST:
this script resets wildcard_inventories to the collection fixture's
pre-state (rare=7, mythic=3), and the watcher sync then moves them
to the fixture log's real values (rare=9, mythic=14).

What it seeds, and why:
- One Card + CardPrint per grpId appearing in the fixture Player.log
  decks (test/fixtures/Player.log — built from REAL log lines), ids
  in the 5001+ range, names "Watcher Fixture Card <grpId>",
  arena_id = the grpId. EXCEPT grpId 75587 (a real Jeskai Artifacts
  card): deliberately left unregistered, so the smoke can watch the
  sync count it unmatched and store it nameless instead of dropping
  or inventing it.
- Watcher tables wiped (the scratch DB's user_decks /
  user_deck_cards hold only fixture state).

Expected sync of the fixture log (see test/api-smoke.js watcher legs):
  decks_stored=2, card_rows=32, cards_matched=31, cards_unmatched=1,
  wildcards afterwards {rare: 9, mythic: 14}.
"""
import json
import os
import sys

from sqlalchemy import create_engine, text

FIXTURE_USER_ID = "11111111-1111-1111-1111-111111111111"
UNREGISTERED_GRP = 75587  # real Jeskai Artifacts grpId, kept out on purpose
ID_BASE = 5001

FIXTURE_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "Player.log"
)


def fixture_grp_ids():
    grp_ids = set()
    with open(FIXTURE_LOG, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s.startswith("{"):
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            for deck in (obj.get("Decks") or {}).values():
                for board in ("MainDeck", "Sideboard", "CommandZone", "Companions"):
                    for entry in deck.get(board) or []:
                        grp_ids.add(int(entry["cardId"]))
    return sorted(grp_ids)


def main():
    url = os.environ.get("SYNC_DATABASE_URL")
    if not url:
        print("SYNC_DATABASE_URL is not set; refusing to guess a database.")
        return 1
    grp_ids = fixture_grp_ids()
    engine = create_engine(url)
    statements = [
        "DELETE FROM user_deck_cards",
        "DELETE FROM user_decks",
        f"DELETE FROM card_prints WHERE id >= {ID_BASE} AND id < {ID_BASE + 1000}",
        f"DELETE FROM cards WHERE id >= {ID_BASE} AND id < {ID_BASE + 1000}",
        # Deterministic wildcard pre-state = the collection fixture's.
        "DELETE FROM wildcard_inventories",
        "INSERT INTO wildcard_inventories (user_id, common, uncommon, rare, mythic) VALUES "
        f"('{FIXTURE_USER_ID}', 0, 0, 7, 3)",
    ]
    seeded = 0
    for i, grp in enumerate(grp_ids):
        if grp == UNREGISTERED_GRP:
            continue
        cid = ID_BASE + i
        statements.append(
            "INSERT INTO cards (id, oracle_id, name, types) VALUES "
            f"({cid}, 'oracle-watcher-{grp}', 'Watcher Fixture Card {grp}', ARRAY['Creature'])"
        )
        statements.append(
            "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity, arena_id) VALUES "
            f"({cid}, {cid}, 'watcher-print-{grp}', 'FIX', '{grp}', 'common', {grp})"
        )
        seeded += 1
    statements.append("SELECT setval('cards_id_seq', 6000)")
    statements.append("SELECT setval('card_prints_id_seq', 6000)")
    with engine.begin() as conn:
        user = conn.execute(
            text("SELECT count(*) FROM users WHERE id = :uid"), {"uid": FIXTURE_USER_ID}
        ).scalar()
        if user != 1:
            print("Fixture user missing — run test/collection_fixture.py first.")
            return 1
        for stmt in statements:
            conn.execute(text(stmt))
    print(f"[+] Slice 5 watcher fixture seeded: {seeded} grpId prints registered, "
          f"grpId {UNREGISTERED_GRP} deliberately unregistered.")
    print("    Expect watcher sync: decks_stored=2 card_rows=32 matched=31 "
          "unmatched=1; wildcards after sync {rare: 9, mythic: 14}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
