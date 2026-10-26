#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 3 decks fixture — seeds the scratch Postgres (the same one
test/collection_fixture.py prepares) with a tiny, hand-computable deck
corpus for the desktop smoke test's decks legs.

    SYNC_DATABASE_URL=postgresql://arena@127.0.0.1:54329/arena_fixture \\
    DATABASE_URL=postgresql+asyncpg://arena@127.0.0.1:54329/arena_fixture \\
      python3 test/decks_fixture.py            # phase 1: Deck A only
      python3 test/decks_fixture.py --phase2   # adds Deck B + re-analyzes

Run AFTER test/collection_fixture.py (it reuses that fixture's user and
leaves its cards/collections alone). NEVER point this at a shared
database: it wipes and re-seeds decks, deck_cards and deck_analyses,
plus its own card/print id ranges and the collection rows for them.

Fixture design (every smoke expectation derives from this by hand):
- Cards carry type_line + subtypes exactly as the fixed seed stores
  them (Slice 3 / KB gap #7): the Dino is "Creature — Dinosaur", the
  Land is "Basic Land — Forest".
- Deck A "Fixture Dino Tribal" (id 3001; winrate 55.0, meta_share 5.0):
  Dino x4, Elf x4, Bolt x2, Land x4 = 14 required. The fixture user
  owns Dino x2, Elf x4, Land x4 (no Bolt) = 10 owned, 71.4% complete.
  Missing: Dino x2 (rare -> 2 rare wildcards), Bolt x2. WC {rare 2,
  mythic 0}.
- Deck B "Fixture Wurm Ramp" (id 3002, phase 2; winrate 52.0,
  meta_share 4.0): Wurm x3, Elf x4, Land x4 = 11 required; owns 8,
  72.7% complete; missing Wurm x3 -> WC {rare 0, mythic 3}.
- Analysis is produced by the engine's OWN deck_analysis.analyze_decks
  (this script runs it), so the stored rows are real engine output.
  Hand-check, Deck A: meta = 55*.7 + 5*.3 = 40.0; mana — avg MV with
  the engine's (mana_value or 2.0) land rule = (4*4 + 1*4 + 1*2 +
  2.0*4)/14 = 30/14 ~= 2.14 -> in the 2.0-3.2 band -> 95.0; synergy =
  0 (no card tags in the fixture); consistency — 3 of 4 distinct cards
  at 4 copies = 75.0; final = 40*.40 + 0*.25 + 75*.20 + 95*.15 = 45.25.
  Deck B: meta = 52*.7 + 4*.3 = 37.6; mana avg = (6*3 + 1*4 + 2.0*4)/11
  = 30/11 ~= 2.73 -> 95.0; consistency 2/3 = 66.67; final ~= 42.62.
"""
import asyncio
import os
import sys

from sqlalchemy import create_engine, text

# Same fixture user as test/collection_fixture.py.
FIXTURE_USER_ID = "11111111-1111-1111-1111-111111111111"
DASH = chr(8212)  # em-dash

CARD_STATEMENTS = [
    "DELETE FROM deck_analyses",
    "DELETE FROM deck_cards",
    "DELETE FROM decks",
    "DELETE FROM user_collections WHERE card_id BETWEEN 2001 AND 2999",
    "DELETE FROM card_prints WHERE id BETWEEN 2101 AND 2999",
    "DELETE FROM cards WHERE id BETWEEN 2001 AND 2999",
    # Cards: type_line + subtypes are what the fixed seed stores.
    "INSERT INTO cards (id, oracle_id, name, mana_cost, mana_value, colors, color_identity, types, type_line, subtypes, keywords) VALUES "
    f"(2001, 'oracle-fixture-dino', 'Fixture Dino', '{{3}}{{G}}', 4.0, ARRAY['G'], ARRAY['G'], ARRAY['Creature'], 'Creature {DASH} Dinosaur', ARRAY['Dinosaur'], ARRAY[]::varchar[])",
    "INSERT INTO cards (id, oracle_id, name, mana_cost, mana_value, colors, color_identity, types, type_line, subtypes, keywords) VALUES "
    f"(2002, 'oracle-fixture-elf', 'Fixture Elf', '{{G}}', 1.0, ARRAY['G'], ARRAY['G'], ARRAY['Creature'], 'Creature {DASH} Elf Druid', ARRAY['Elf', 'Druid'], ARRAY[]::varchar[])",
    "INSERT INTO cards (id, oracle_id, name, mana_cost, mana_value, colors, color_identity, types, type_line, subtypes, keywords) VALUES "
    "(2003, 'oracle-fixture-bolt', 'Fixture Bolt', '{R}', 1.0, ARRAY['R'], ARRAY['R'], ARRAY['Instant'], 'Instant', ARRAY[]::varchar[], ARRAY[]::varchar[])",
    "INSERT INTO cards (id, oracle_id, name, mana_cost, mana_value, colors, color_identity, types, type_line, subtypes, keywords) VALUES "
    f"(2004, 'oracle-fixture-land', 'Fixture Land', NULL, 0.0, ARRAY[]::varchar[], ARRAY['G'], ARRAY['Basic', 'Land'], 'Basic Land {DASH} Forest', ARRAY['Forest'], ARRAY[]::varchar[])",
    "INSERT INTO cards (id, oracle_id, name, mana_cost, mana_value, colors, color_identity, types, type_line, subtypes, keywords) VALUES "
    f"(2005, 'oracle-fixture-wurm', 'Fixture Wurm', '{{4}}{{G}}{{G}}', 6.0, ARRAY['G'], ARRAY['G'], ARRAY['Creature'], 'Creature {DASH} Wurm', ARRAY['Wurm'], ARRAY[]::varchar[])",
    # Prints: one per card, rarities drive the wildcard math.
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(2101, 2001, 'fixture-dino-print', 'FIX', '1', 'rare')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(2102, 2002, 'fixture-elf-print', 'FIX', '1', 'common')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(2103, 2003, 'fixture-bolt-print', 'FIX', '1', 'uncommon')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(2104, 2004, 'fixture-land-print', 'FIX', '1', 'common')",
    "INSERT INTO card_prints (id, card_id, scryfall_id, set_code, collector_number, rarity) VALUES "
    "(2105, 2005, 'fixture-wurm-print', 'FIX', '1', 'mythic')",
    # Ownership for the fixture user: Dino x2, Elf x4, Land x4.
    "INSERT INTO user_collections (user_id, card_id, quantity) VALUES "
    f"('{FIXTURE_USER_ID}', 2001, 2)",
    "INSERT INTO user_collections (user_id, card_id, quantity) VALUES "
    f"('{FIXTURE_USER_ID}', 2002, 4)",
    "INSERT INTO user_collections (user_id, card_id, quantity) VALUES "
    f"('{FIXTURE_USER_ID}', 2004, 4)",
    "SELECT setval('cards_id_seq', 3000)",
    "SELECT setval('card_prints_id_seq', 3000)",
]

DECK_A_STATEMENTS = [
    "INSERT INTO decks (id, name, archetype, format, tier, winrate, meta_share) VALUES "
    "(3001, 'Fixture Dino Tribal', 'Dino Tribal', 'Standard', 2, 55.0, 5.0)",
    "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3001, 2001, 4)",
    "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3001, 2002, 4)",
    "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3001, 2003, 2)",
    "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3001, 2004, 4)",
    "SELECT setval('decks_id_seq', 4000)",
]

DECK_B_STATEMENTS = [
    "INSERT INTO decks (id, name, archetype, format, tier, winrate, meta_share) VALUES "
    "(3002, 'Fixture Wurm Ramp', 'Ramp', 'Standard', 3, 52.0, 4.0)",
    "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3002, 2005, 3)",
    "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3002, 2002, 4)",
    "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3002, 2004, 4)",
    "SELECT setval('decks_id_seq', 4000)",
]


def run_statements(engine, statements):
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def main():
    phase2 = "--phase2" in sys.argv
    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url or "postgresql" not in sync_url:
        print("Set SYNC_DATABASE_URL to the scratch Postgres first (see header).")
        sys.exit(1)
    if not os.environ.get("DATABASE_URL"):
        print("Set DATABASE_URL too — the engine's analyze_decks reads it.")
        sys.exit(1)

    engine = create_engine(sync_url)
    if phase2:
        run_statements(engine, DECK_B_STATEMENTS)
        print("[+] Phase 2: Deck B added.")
    else:
        run_statements(engine, CARD_STATEMENTS + DECK_A_STATEMENTS)
        print("[+] Phase 1: cards + Deck A seeded.")

    # The stored analysis must be the engine's own output, not fixture
    # arithmetic: run the real batch analyzer against this database.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from apps.api.deck_analysis import analyze_decks

    asyncio.run(analyze_decks())
    print("[+] deck_analysis.analyze_decks() run — stored rows are engine output.")


if __name__ == "__main__":
    main()
