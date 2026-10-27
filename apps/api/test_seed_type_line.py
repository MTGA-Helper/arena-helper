#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 3 unit check for seed_cards.parse_type_line (KB gap #7).

Run from the repo root with the API venv:

    PYTHONPATH=. python3 apps/api/test_seed_type_line.py

Plain asserts, matching the repo's script-style checks: the cases are
real Scryfall type lines, and each expectation is what tribal analysis
needs to find in Card.subtypes once the seed stores them.
"""
from apps.api.seed_cards import parse_type_line

DASH = chr(8212)  # em-dash, as Scryfall prints it

CASES = [
    # (type_line, expected types, expected subtypes)
    (f"Creature {DASH} Dinosaur", ["Creature"], ["Dinosaur"]),
    (f"Legendary Creature {DASH} Elf Druid", ["Legendary", "Creature"], ["Elf", "Druid"]),
    (f"Creature {DASH} Cat Soldier", ["Creature"], ["Cat", "Soldier"]),
    (f"Basic Land {DASH} Forest", ["Basic", "Land"], ["Forest"]),
    (f"Legendary Planeswalker {DASH} Ajani", ["Legendary", "Planeswalker"], ["Ajani"]),
    (f"Artifact Creature {DASH} Golem", ["Artifact", "Creature"], ["Golem"]),
    ("Instant", ["Instant"], []),
    ("Sorcery", ["Sorcery"], []),
    ("", [], []),
    (None, [], []),
]


def main():
    for type_line, want_types, want_subtypes in CASES:
        got_types, got_subtypes = parse_type_line(type_line)
        assert got_types == want_types, (type_line, got_types, want_types)
        assert got_subtypes == want_subtypes, (type_line, got_subtypes, want_subtypes)
        print(f"PASS - {type_line!r} -> types={got_types} subtypes={got_subtypes}")
    print(f"RESULT: ALL PASS ({len(CASES)} cases)")


if __name__ == "__main__":
    main()
