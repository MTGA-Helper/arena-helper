#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 4 unit checks for the wildcard math (TURBO surge, Oct 26, 2026).

Run from the repo root with the API venv:

    PYTHONPATH=. python3 apps/api/test_slice4_wildcard_math.py

Plain asserts in the repo's script style. Covers:
- recommendations._craft_bucket normalization;
- recommendations._deck_tally — cheapest-print pricing, all four
  rarity buckets tallied, basic lands free, print fan-out counted
  once — including THE acceptance case: Matt's Jund Dino Madness
  against Billy's collection must total 41 wildcards =
  10 mythic / 25 rare / 5 uncommon / 1 common. The per-card print
  rarity sets below were read from the seeded card corpus
  (arena_seed, 2026-10-26) and the ownership column is the Oct 19,
  2026 hand-built table (matt-jund-dino-madness-deck-lab-submission
  -oct19.md) — the same numbers the integration leg re-proves
  against the real database (apps/desktop/test/jund_fixture.py);
- craft_priority.build_craft_priorities — KB gap #12: a card's
  craft cost is the copies to craft ONCE (largest single-deck
  deficit), not the sum of its deficits across decks.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
# apps/api itself: recommendations.py imports `services...` and
# models.py imports `database` as top-level modules (the deployed
# tree's own convention when uvicorn runs apps.api.main).
sys.path.insert(0, os.path.dirname(__file__))

from apps.api.recommendations import _craft_bucket, _deck_tally
from apps.api.craft_priority import build_craft_priorities

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL") + " - " + name + ((" " + detail) if detail else ""))
    if not cond:
        FAILURES.append(name)


def rows_for(card_id, qty, name, rarities, types):
    """One tally row per print — the fan-out the endpoints query."""
    return [(card_id, qty, name, r, types) for r in rarities]


# --- _craft_bucket -----------------------------------------------------

check("bucket: common/uncommon/rare pass through",
      [_craft_bucket(r) for r in ("common", "uncommon", "rare")] == ["common", "uncommon", "rare"])
check("bucket: mythic tier normalizes to mythic",
      all(_craft_bucket(r) == "mythic" for r in ("mythic", "special", "masterpiece", "bonus")))
check("bucket: unknown rarity prices as rare, None as common",
      _craft_bucket("weird") == "rare" and _craft_bucket(None) == "common")

# --- _deck_tally: the pricing rules ------------------------------------

# Fabled Passage shape: prints span mythic + rare; crafting costs the
# CHEAPEST printing (rare). Pre-fix math charged the mythic.
rows = rows_for(1, 4, "Multi Print", ["mythic", "rare", "rare"], ["Land"])
_d, req, owned, missing, wc, craft = _deck_tally(rows, {1: 3})
check("cheapest print prices the deficit (Fabled Passage shape)",
      req == 4 and owned == 3 and wc == {"common": 0, "uncommon": 0, "rare": 1, "mythic": 0}
      and missing == [{"name": "Multi Print", "quantity": 1, "rarity": "rare"}]
      and craft[1] == "rare",
      str(wc))

# Uncommon + common deficits are tallied, not dropped (pre-fix: only
# rare/mythic were counted at all).
rows = (rows_for(2, 4, "Unc", ["uncommon"], ["Instant"])
        + rows_for(3, 4, "Com", ["common", "rare"], ["Sorcery"]))
_d, req, owned, missing, wc, craft = _deck_tally(rows, {2: 1, 3: 3})
check("uncommon/common deficits tallied in their own buckets",
      wc == {"common": 1, "uncommon": 3, "rare": 0, "mythic": 0}, str(wc))

# Basic lands are free: unowned basics count as owned, never missing,
# never costed — even with a rare print in the fan-out.
rows = rows_for(4, 3, "Mountain", ["common", "rare"], ["Basic", "Land"])
_d, req, owned, missing, wc, craft = _deck_tally(rows, {})
check("basic lands are free (unowned, rare print and all)",
      req == 3 and owned == 3 and missing == []
      and wc == {"common": 0, "uncommon": 0, "rare": 0, "mythic": 0},
      str((req, owned, missing, wc)))

# A mythic-only card prices mythic.
rows = rows_for(5, 4, "Mythic Only", ["mythic"], ["Creature"])
_d, req, owned, missing, wc, craft = _deck_tally(rows, {5: 2})
check("mythic-only card prices mythic", wc["mythic"] == 2 and craft[5] == "mythic", str(wc))

# --- THE ACCEPTANCE CASE: Jund Dino Madness vs Billy's collection ------
# (name, qty needed, copies owned, print rarities, types)
# Print rarity sets read from the seeded corpus 2026-10-26; ownership
# from the Oct 19 hand-built table. Basics are not in the collection
# (free on Arena).
JUND = [
    ("Thornspire Verge", 2, 1, ["rare"], ["Land"]),
    ("Fabled Passage", 4, 3, ["mythic", "rare"], ["Land"]),
    ("Mountain", 3, 0, ["common", "rare"], ["Basic", "Land"]),
    ("Wastewood Verge", 4, 1, ["rare"], ["Land"]),
    ("Forest", 1, 0, ["common", "rare"], ["Basic", "Land"]),
    ("Blazemire Verge", 4, 1, ["rare"], ["Land"]),
    ("Cavern of Souls", 2, 1, ["mythic", "rare"], ["Land"]),
    ("Commercial District", 1, 1, ["rare"], ["Land"]),
    ("Swamp", 2, 0, ["common", "rare"], ["Basic", "Land"]),
    ("Stomping Ground", 1, 2, ["mythic", "rare"], ["Land"]),
    ("Raucous Theater", 1, 1, ["rare"], ["Land"]),
    ("Raph & Mikey, Troublemakers", 2, 0, ["rare"], ["Legendary", "Creature"]),
    ("Rakdos Joins Up", 4, 1, ["rare"], ["Legendary", "Enchantment"]),
    ("Seize the Spoils", 4, 3, ["common", "rare"], ["Sorcery"]),
    ("Foggy Swamp Visions", 4, 0, ["rare"], ["Sorcery"]),
    ("Gishath, Sun's Avatar", 4, 2, ["mythic"], ["Legendary", "Creature"]),
    ("Ghalta, Stampede Tyrant", 4, 1, ["mythic"], ["Legendary", "Creature"]),
    ("Trumpeting Carnosaur", 3, 1, ["rare"], ["Creature"]),
    ("Vaultborn Tyrant", 3, 1, ["mythic"], ["Creature"]),
    ("Collector's Vault", 3, 1, ["uncommon"], ["Artifact"]),
    ("Bitter Triumph", 4, 1, ["rare", "uncommon"], ["Instant"]),
    ("Smuggler's Surprise", 4, 1, ["rare"], ["Instant"]),
    ("Overlord of the Hauntwoods", 4, 1, ["mythic"], ["Enchantment", "Creature"]),
    ("Ghost Vacuum", 3, 1, ["rare"], ["Artifact"]),
]

rows = []
collection = {}
for i, (name, qty, own, rarities, types) in enumerate(JUND, start=100):
    rows += rows_for(i, qty, name, rarities, types)
    if own:
        collection[i] = own
_d, req, owned, missing, wc, craft = _deck_tally(rows, collection)
missing_total = sum(m["quantity"] for m in missing)
check("JUND ACCEPTANCE: 41 wildcards = 10M / 25R / 5U / 1C",
      wc == {"common": 1, "uncommon": 5, "rare": 25, "mythic": 10} and missing_total == 41,
      f"wc={wc} missing_total={missing_total}")
check("JUND ACCEPTANCE: 71 required / 30 owned (basics free)",
      req == 71 and owned == 30, f"req={req} owned={owned}")
check("JUND ACCEPTANCE: discriminating cards priced at cheapest print",
      craft[101] == "rare"      # Fabled Passage (has mythic prints)
      and craft[106] == "rare"  # Cavern of Souls (has mythic prints)
      and craft[113] == "common"   # Seize the Spoils (has a rare print)
      and craft[120] == "uncommon",  # Bitter Triumph (has rare prints)
      str({k: craft[k] for k in (101, 106, 113, 120)}))

# --- craft_priority.build_craft_priorities (KB gap #12) ----------------

decks = [
    {"deck_name": "Deck A", "deck_score": 50.0, "cards": [
        {"card_id": 1, "card_name": "Shared Card", "quantity": 4, "rarity": "rare"},
        {"card_id": 2, "card_name": "Owned Card", "quantity": 4, "rarity": "uncommon"},
    ]},
    {"deck_name": "Deck B", "deck_score": 50.0, "cards": [
        {"card_id": 1, "card_name": "Shared Card", "quantity": 4, "rarity": "rare"},
    ]},
]
ranked = build_craft_priorities(decks, {1: 2, 2: 4})
shared = next((r for r in ranked if r["card_name"] == "Shared Card"), None)
check("craft cost is copies-to-craft-once, not the cross-deck sum",
      shared is not None and shared["cost"] == 2 and len(shared["unlocks"]) == 2,
      str(shared))
# Deficits: Deck A needs 2 more, Deck B needs 2 more -> ONE craft of 2
# serves both. (A deck needing 4 against 1 owned is the max case:)
decks2 = [
    {"deck_name": "Deck A", "deck_score": 50.0, "cards": [
        {"card_id": 1, "card_name": "Shared Card", "quantity": 2, "rarity": "rare"}]},
    {"deck_name": "Deck B", "deck_score": 50.0, "cards": [
        {"card_id": 1, "card_name": "Shared Card", "quantity": 4, "rarity": "rare"}]},
]
ranked2 = build_craft_priorities(decks2, {1: 1})
check("craft cost is the LARGEST single-deck deficit (max, not sum)",
      ranked2[0]["cost"] == 3, str(ranked2[0]))
check("fully owned cards are not craft candidates",
      all(r["card_name"] != "Owned Card" for r in ranked), str(ranked))
# Basic lands are free on Arena — never craft candidates, even when
# the collection holds none (the pre-fix report ranked a Forest #1).
decks3 = [
    {"deck_name": "Deck A", "deck_score": 50.0, "cards": [
        {"card_id": 9, "card_name": "Forest", "quantity": 4,
         "rarity": "common", "is_basic": True}]},
]
check("basic lands are never craft candidates",
      build_craft_priorities(decks3, {}) == [])
check("score formula runs on the corrected cost",
      shared is not None and abs(shared["score"] - (100.0 * 2) / (2 * 0.5)) < 0.01,
      str(shared and shared["score"]))

print()
if FAILURES:
    print(f"RESULT: {len(FAILURES)} FAILURES")
    sys.exit(1)
print("RESULT: ALL PASS")
