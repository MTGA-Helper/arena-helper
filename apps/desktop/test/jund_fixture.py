#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 4 Jund Dino acceptance fixture — seeds a SCRATCH CLONE of the
full card corpus with Matt's "Jund Dino Madness" Deck Lab submission
(deck_lab_submissions id=3, Oct 17, 2026) as an engine deck, plus
Billy's collection at the ownership the Oct 19, 2026 hand-built
analysis recorded (files/matt-jund-dino-madness-deck-lab-submission
-oct19.md).

    createdb -h /tmp -p 54329 -U arena arena_slice4 -T arena_seed
    SYNC_DATABASE_URL=<redacted>
        python3 test/jund_fixture.py

NEVER point this at a shared database: it wipes and re-seeds users,
user_collections, wildcard_inventories, decks, deck_cards and
deck_analyses. The card corpus itself (cards / card_prints) is only
READ — card ids are resolved by exact name, so the seeded prints are
the real Scryfall prints the production seed carries.

The acceptance expectation (hand-built Oct 19 against production,
and the deck-choosing build spec's Phase 1 test case): completing
this deck costs exactly 41 wildcards = 10 mythic / 25 rare /
5 uncommon / 1 common, priced at each card's CHEAPEST craftable
printing, basics free. 71 copies required, 30 owned (basics count
as owned), completion 42.3%. The discriminating cards — the prints
span rarities, so highest-print pricing (the pre-Slice-4 math)
gets them wrong:
  Fabled Passage   prints mythic+rare  -> crafts RARE
  Cavern of Souls  prints mythic+rare  -> crafts RARE
  Seize the Spoils prints common+rare  -> crafts COMMON
  Bitter Triumph   prints rare+uncommon -> crafts UNCOMMON
"""
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

FIXTURE_USER_ID = "22222222-2222-2222-2222-222222222222"
DECK_ID = 4001

# (exact card name, copies in deck, copies Billy owned Oct 19)
# Own=None for the three basics: free on Arena, no collection row.
# The sideboard (Smuggler's Surprise / Overlord / Ghost Vacuum) is
# part of the 71 — DeckCard has no board flag, and the hand-built
# 41-wildcard total includes it.
JUND = [
    ("Thornspire Verge", 2, 1),
    ("Fabled Passage", 4, 3),
    ("Mountain", 3, None),
    ("Wastewood Verge", 4, 1),
    ("Forest", 1, None),
    ("Blazemire Verge", 4, 1),
    ("Cavern of Souls", 2, 1),
    ("Commercial District", 1, 1),
    ("Swamp", 2, None),
    ("Stomping Ground", 1, 2),
    ("Raucous Theater", 1, 1),
    ("Raph & Mikey, Troublemakers", 2, 0),
    ("Rakdos Joins Up", 4, 1),
    ("Seize the Spoils", 4, 3),
    ("Foggy Swamp Visions", 4, 0),
    ("Gishath, Sun's Avatar", 4, 2),
    ("Ghalta, Stampede Tyrant", 4, 1),
    ("Trumpeting Carnosaur", 3, 1),
    ("Vaultborn Tyrant", 3, 1),
    ("Collector's Vault", 3, 1),
    ("Bitter Triumph", 4, 1),
    ("Smuggler's Surprise", 4, 1),
    ("Overlord of the Hauntwoods", 4, 1),
    ("Ghost Vacuum", 3, 1),
]


def main():
    url = os.environ.get("SYNC_DATABASE_URL")
    if not url or "postgresql" not in url:
        print("Set SYNC_DATABASE_URL to the scratch Postgres clone first (see header).")
        return 1
    # FIX (Oct 26, 2026): hard allowlist BEFORE any DELETE can run.
    # The gate above only checked the URL was set and mentioned
    # "postgresql", so a SYNC_DATABASE_URL pointing at production (or
    # any shared database) would have been wiped by the DELETEs below.
    # Refuse unless BOTH hold, per the header example: the database
    # name is exactly the scratch clone (arena_slice4) AND the target
    # is local (the /tmp unix socket or the scratch port 54329).
    _u = make_url(url)
    _db_name = _u.database or ""
    _host = _u.host or _u.query.get("host", "")
    _port_raw = _u.port or _u.query.get("port", "")
    try:
        _port = int(_port_raw) if _port_raw else None
    except (TypeError, ValueError):
        _port = None
    if not (_db_name == "arena_slice4" and (_host == "/tmp" or _port == 54329)):
        print(
            "ABORT: refusing to run the Jund fixture wipe against "
            f"database={_db_name!r} host={_host!r} port={_port!r}. "
            "This fixture only runs against the local scratch clone "
            "(database 'arena_slice4' on the /tmp socket or port 54329; "
            "see header). Nothing was deleted."
        )
        return 1
    engine = create_engine(url)
    with engine.begin() as conn:
        # Resolve every card by EXACT name first: a miss aborts
        # before anything is wiped.
        card_ids = {}
        for name, _qty, _own in JUND:
            rows = conn.execute(text(
                "SELECT id FROM cards WHERE name = :n ORDER BY id"
            ), {"n": name}).fetchall()
            if len(rows) != 1:
                print(f"ABORT: exact-name lookup for {name!r} returned {len(rows)} rows.")
                return 1
            card_ids[name] = rows[0][0]

        for stmt in [
            "DELETE FROM deck_analyses",
            "DELETE FROM deck_cards",
            "DELETE FROM decks",
            "DELETE FROM user_collections",
            "DELETE FROM wildcard_inventories",
            "DELETE FROM users",
        ]:
            conn.execute(text(stmt))

        conn.execute(text(
            "INSERT INTO users (id, email, hashed_password) VALUES "
            f"('{FIXTURE_USER_ID}', 'billy-fixture@example.com', 'fixture-not-a-login')"
        ))
        conn.execute(text(
            "INSERT INTO decks (id, name, archetype, format, tier, winrate, meta_share, source) VALUES "
            f"({DECK_ID}, 'Jund Dino Madness', 'Jund Dinosaurs', 'Standard', NULL, NULL, NULL, 'deck_lab_submission_3')"
        ))
        for name, qty, own in JUND:
            cid = card_ids[name]
            conn.execute(text(
                "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES "
                f"({DECK_ID}, {cid}, {qty})"
            ))
            if own:
                conn.execute(text(
                    "INSERT INTO user_collections (user_id, card_id, quantity) VALUES "
                    f"('{FIXTURE_USER_ID}', {cid}, {own})"
                ))
        conn.execute(text("SELECT setval('decks_id_seq', 5000)"))

    print("[+] Slice 4 Jund fixture seeded.")
    print("    Expect from the fixed engine: required=71 owned=30 completion=42.3%")
    print("    wildcard_cost = {mythic: 10, rare: 25, uncommon: 5, common: 1} (total 41)")
    print("    craft rarities: Fabled Passage=rare, Cavern of Souls=rare,")
    print("    Seize the Spoils=common, Bitter Triumph=uncommon; basics missing=0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
