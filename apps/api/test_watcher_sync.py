#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 5 unit checks for the watcher's payload shaping (TURBO
surge, Oct 26, 2026).

Run from the repo root with the API venv:

    PYTHONPATH=. python3 apps/api/test_watcher_sync.py

Plain checks in the repo's script style. The endpoint itself is
proven end-to-end by the desktop smoke's watcher legs against the
local fixture stack; what belongs here is the pure half:
normalize_deck_cards decides which rows land, and its rules (merge
duplicates per board, drop non-positive quantities, clamp unknown
boards to main) are pinned here without a database.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from apps.api.watcher import WatcherCardIn, normalize_deck_cards

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL") + " - " + name + ((" " + detail) if detail else ""))
    if not cond:
        FAILURES.append(name)


def rows(*specs):
    return [WatcherCardIn(grp_id=g, quantity=q, board=b) for g, q, b in specs]


out = normalize_deck_cards(rows((101, 2, "main"), (101, 1, "main")))
check("duplicate (grp, board) rows merge", out == [{"grp_id": 101, "board": "main", "quantity": 3}], str(out))

out = normalize_deck_cards(rows((101, 4, "main"), (101, 2, "sideboard")))
check("same grp on two boards stays two rows", out == [
    {"grp_id": 101, "board": "main", "quantity": 4},
    {"grp_id": 101, "board": "sideboard", "quantity": 2},
], str(out))

out = normalize_deck_cards(rows((101, 0, "main"), (102, -1, "main"), (103, 1, "main")))
check("non-positive quantities are dropped", out == [{"grp_id": 103, "board": "main", "quantity": 1}], str(out))

out = normalize_deck_cards(rows((101, 1, "commandzone")))
check("unknown board clamps to main", out == [{"grp_id": 101, "board": "main", "quantity": 1}], str(out))

check("empty input stays empty", normalize_deck_cards([]) == [])

print()
if FAILURES:
    print(f"RESULT: {len(FAILURES)} FAILURES")
    sys.exit(1)
print("RESULT: ALL PASS")
