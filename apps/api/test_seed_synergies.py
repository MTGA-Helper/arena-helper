#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit check for seed_synergies.classify_card / build_pairs (KB §7).

Run from the repo root with the API venv:

    PYTHONPATH=. python3 apps/api/test_seed_synergies.py

Plain asserts, repo style. The oracle texts are the real wordings
of the named cards (abridged only where the abridgement keeps every
signal phrase intact).
"""
import sys
import types as _types

# seed_synergies imports sqlalchemy only inside main(); the module
# itself is import-safe without a database.
from apps.api.seed_synergies import classify_card, build_pairs

CASES = [
    # (oracle_text, keywords, types, want_producers, want_payoffs)
    # Soul Warden — lifegain producer (event text).
    ("Whenever another creature enters, you gain 1 life.",
     [], ["Creature"], {"lifegain"}, set()),
    # Ajani's Pridemate — lifegain payoff + counter producer.
    ("Whenever you gain life, put a +1/+1 counter on this creature.",
     [], ["Creature"], {"counters"}, {"lifegain"}),
    # A lifelink body — producer via the keyword alone.
    ("Flying, lifelink", ["Flying", "Lifelink"], ["Creature"],
     {"lifegain"}, set()),
    # Seize the Spoils — discard (yard stocking) + draw + Treasure
    # (ramp producer, via the Treasure-token shape).
    ("As an additional cost to cast this spell, discard a card. "
     "Draw two cards and create a Treasure token.",
     [], ["Sorcery"],
     {"graveyard", "draw", "landfall", "tokens", "spellcast"}, set()),
    # Trumpeting Carnosaur — discard outlet in hand.
    ("Trample. Discard a card: Discover 5.",
     [], ["Creature"], {"graveyard"}, set()),
    # Rakdos Joins Up — return-from-graveyard payoff.
    ("When Rakdos Joins Up enters, return target creature card from "
     "your graveyard to the battlefield with two additional +1/+1 "
     "counters on it.",
     [], ["Enchantment"], set(), {"graveyard"}),
    # A prowess threat — spellcast payoff via keyword.
    ("Prowess (Whenever you cast a noncreature spell, this creature "
     "gets +1/+1 until end of turn.)",
     ["Prowess"], ["Creature"], set(), {"spellcast"}),
    # A bolt — the spell itself is a spellcast producer.
    ("This spell deals 3 damage to any target.",
     [], ["Instant"], {"spellcast"}, set()),
    # A vanilla bear — no signals at all.
    ("", [], ["Creature"], set(), set()),
]


def main():
    for text, kws, types_, want_p, want_y in CASES:
        got_p, got_y = classify_card(text, kws, types_)
        assert got_p == want_p, (text[:40], "producers", got_p, want_p)
        assert got_y == want_y, (text[:40], "payoffs", got_y, want_y)
        print(f"PASS - classify {text[:44]!r} -> prod={sorted(got_p)} "
              f"pay={sorted(got_y)}")

    cards = [
        {"id": 1, "name": "Soul Warden",
         "oracle_text": "Whenever another creature enters, you gain 1 life.",
         "keywords": [], "types": ["Creature"]},
        {"id": 2, "name": "Ajani's Pridemate",
         "oracle_text": "Whenever you gain life, put a +1/+1 counter on "
                        "this creature.",
         "keywords": [], "types": ["Creature"]},
        {"id": 3, "name": "Grizzly Bears", "oracle_text": "",
         "keywords": [], "types": ["Creature"]},
    ]
    pairs = build_pairs(cards)
    assert len(pairs) == 1, pairs
    a, b, t, _r = pairs[0]
    assert (a, b, t) == (1, 2, "lifegain_engine"), pairs
    print("PASS - build_pairs wires producer -> payoff, skips the vanilla")
    print(f"RESULT: ALL PASS ({len(CASES) + 1} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
