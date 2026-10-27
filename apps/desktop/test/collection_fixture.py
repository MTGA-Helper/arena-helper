#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 2 collection fixture — seeds a scratch Postgres with a tiny,
hand-computable card corpus for the desktop smoke test's upload round-trip.

    SYNC_DATABASE_URL=postgresql://arena@127.0.0.1:54329/arena_fixture \
      python3 test/collection_fixture.py

NEVER point this at a shared database: it wipes and re-seeds the users,
cards, card_prints, user_collections and wildcard_inventories tables.

Fixture design (every smoke expectation derives from this by hand):
- "Fixture Alpha" has THREE prints; its canonical print (smallest print id,
  101) is rare, print 102 is mythic, print 103 is rare. The Phase 0 stats
  fix counts a card once, through its canonical print: owning Alpha counts
  toward rares only. (The pre-fix fan-out query would count Alpha's copies
  once per print: rares AND mythics both inflated.)
- "Fixture Beta" single print, mythic. "Fixture Gamma" common.
  "Fixture Delta" uncommon.
- One user (fixture@example.com) with wildcard inventory rare=7, mythic=3.
- user_collections starts EMPTY; the smoke test's CSV upload fills it.

Expected after the smoke test uploads its CSV #1 (see test/api-smoke.js):
  upload response: cards_imported=11, unique_cards=4, matched_cards=5,
                   unmatched_cards=1, duplicates=1
  GET /collection: 4 rows — Alpha x4, Beta x2, Gamma x4, Delta x1
  GET /collection/stats: total_cards=11, unique_cards=4, rares=4, mythics=2,
                   wildcards {rare: 7, mythic: 3}
  (The buggy pre-fix stats query would report rares=8, mythics=6 here.)
"""
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

FIXTURE_USER_ID = "11111111-1111-1111-1111-111111111111"

STATEMENTS = [
    # Slice 5: the watcher's tables reference cards too — clear them
    # before the card wipe or the foreign key refuses it on re-runs.
    # FIX (Oct 26, 2026; hub #329): every wipe below is scoped to
    # this fixture's own id domain — the fixture user, and card/print
    # ids below 1000 (the fixture inserts cards 1-4 and prints 101-106
    # explicitly and parks both sequences at 1000). They used to be
    # unscoped —
    #   "DELETE FROM user_deck_cards", "DELETE FROM user_decks",
    #   "DELETE FROM user_collections",
    #   "DELETE FROM wildcard_inventories", "DELETE FROM card_prints",
    #   "DELETE FROM cards", "DELETE FROM users",
    # — full-table wipes of whatever database the URL named. The
    # allowlist in main() is the second lock; these scopes are the
    # first. user_deck_cards is keyed by deck, so it is scoped through
    # the fixture user's own watcher decks.
    "DELETE FROM user_deck_cards WHERE deck_id IN "
    f"(SELECT id FROM user_decks WHERE user_id = '{FIXTURE_USER_ID}')",
    f"DELETE FROM user_decks WHERE user_id = '{FIXTURE_USER_ID}'",
    f"DELETE FROM user_collections WHERE user_id = '{FIXTURE_USER_ID}'",
    f"DELETE FROM wildcard_inventories WHERE user_id = '{FIXTURE_USER_ID}'",
    "DELETE FROM card_prints WHERE id BETWEEN 1 AND 999",
    "DELETE FROM cards WHERE id BETWEEN 1 AND 999",
    f"DELETE FROM users WHERE id = '{FIXTURE_USER_ID}'",
    # One fixture user; the collection routes' Phase 1 stub dependency
    # resolves "the current user" as the first user with a collection.
    "INSERT INTO users (id, email, hashed_password) VALUES "
    f"('{FIXTURE_USER_ID}', 'fixture@example.com', 'fixture-not-a-login')",
    # Cards: oracle_id is unique/not-null; types is the seeded type list
    # the /collection payload returns.
    "INSERT INTO cards (id, oracle_id, name, types) VALUES "
    "(1, 'oracle-fixture-alpha', 'Fixture Alpha', ARRAY['Creature'])",
    "INSERT INTO cards (id, oracle_id, name, types) VALUES "
    "(2, 'oracle-fixture-beta', 'Fixture Beta', ARRAY['Instant'])",
    "INSERT INTO cards (id, oracle_id, name, types) VALUES "
    "(3, 'oracle-fixture-gamma', 'Fixture Gamma', ARRAY['Sorcery'])",
    "INSERT INTO cards (id, oracle_id, name, types) VALUES "
    "(4, 'oracle-fixture-delta', 'Fixture Delta', ARRAY['Enchantment'])",
    # Prints: explicit ids make Alpha's canonical print deterministic
    # (101 = rare). Print 102 being mythic is the fan-out tripwire.
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(101, 1, 'fixture-alpha-print-1', 'FIX', '1', 'rare')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(102, 1, 'fixture-alpha-print-2', 'FIX', '2', 'mythic')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(103, 1, 'fixture-alpha-print-3', 'FIX', '3', 'rare')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(104, 2, 'fixture-beta-print-1', 'FIX', '1', 'mythic')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(105, 3, 'fixture-gamma-print-1', 'FIX', '1', 'common')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(106, 4, 'fixture-delta-print-1', 'FIX', '1', 'uncommon')",
    # Keep the sequences ahead of the explicit ids.
    "SELECT setval('cards_id_seq', 1000)",
    "SELECT setval('card_prints_id_seq', 1000)",
    "INSERT INTO wildcard_inventories (user_id, common, uncommon, rare, mythic) VALUES "
    f"('{FIXTURE_USER_ID}', 0, 0, 7, 3)",
]


def require_scratch_db(url):
    # FIX (Oct 26, 2026; hub #329): hard allowlist, mirroring the
    # jund_fixture guard landed earlier today. The check in main()
    # only required SYNC_DATABASE_URL to be SET, so a production URL
    # satisfied it — and the statements above would then have wiped
    # and re-seeded the collection tables in production. This
    # fixture's scratch target (see header) is the database
    # 'arena_fixture' on the local scratch cluster: the /tmp unix
    # socket or port 54329. Refuse anything else, before the engine
    # is even created.
    u = make_url(url)
    db_name = u.database or ""
    host = u.host or u.query.get("host", "")
    port_raw = u.port or u.query.get("port", "")
    try:
        port = int(port_raw) if port_raw else None
    except (TypeError, ValueError):
        port = None
    if not (db_name == "arena_fixture" and (host == "/tmp" or port == 54329)):
        print(
            "ABORT: refusing to run the collection fixture against "
            f"database={db_name!r} host={host!r} port={port!r}. This "
            "fixture only runs against the local scratch database "
            "(database 'arena_fixture' on the /tmp socket or port "
            "54329; see header). Nothing was deleted."
        )
        return False
    return True


def main():
    url = os.environ.get("SYNC_DATABASE_URL")
    if not url:
        print("SYNC_DATABASE_URL is not set; refusing to guess a database.")
        return 1
    if not require_scratch_db(url):
        return 1
    engine = create_engine(url)
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            conn.execute(text(stmt))
    print("[+] Slice 2 collection fixture seeded.")
    print("    Expect after CSV #1 upload: imported=11 unique=4 matched=5 "
          "unmatched=1 duplicates=1; stats total=11 unique=4 rares=4 "
          "mythics=2 wildcards={rare:7, mythic:3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
