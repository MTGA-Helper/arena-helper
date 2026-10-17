# -*- coding: utf-8 -*-
"""
Tests for the synergy derivation slice (Phase 2).

The derivation tests are pure: fixture rosters + tag maps, no database.
The row-builder test only instantiates an ORM object; it never opens a
session or touches a live database.

Run from the repo root:
    PYTHONPATH=. apps/api pytest apps/api/test_synergy_derivation.py
(or anywhere with apps/api and the repo root on sys.path.)
"""
import pytest

from apps.api.synergy_derivation import (
    SYNERGY_TYPE_CO_OCCURRENCE,
    SYNERGY_TYPE_SHARED_TAG,
    DeckRoster,
    derive_synergies,
    weighted_tag_overlap,
)

# --- Fixtures -------------------------------------------------------------
# Cards 1..5. Card 4 deliberately has no tags.
TAGS = {
    1: {"ramp": 1.0, "lifegain": 0.5},
    2: {"ramp": 1.0},
    3: {"removal": 1.0},
    4: {},
    5: {"removal": 1.0, "counterspell": 1.0},
}

DECKS = [
    DeckRoster(deck_id=1, format="Standard", card_ids=[1, 2, 3]),
    DeckRoster(deck_id=2, format="Standard", card_ids=[1, 2]),
    DeckRoster(deck_id=3, format="Standard", card_ids=[2, 3, 5]),
    DeckRoster(deck_id=4, format="Historic", card_ids=[1, 4]),
]


def by_pair(rows):
    return {(r.format, r.card_a_id, r.card_b_id): r for r in rows}


# --- weighted_tag_overlap --------------------------------------------------

def test_tag_overlap_identical_sets():
    assert weighted_tag_overlap({"ramp": 1.0}, {"ramp": 1.0}) == 1.0


def test_tag_overlap_disjoint_and_empty():
    assert weighted_tag_overlap({"ramp": 1.0}, {"removal": 1.0}) == 0.0
    assert weighted_tag_overlap({}, {"removal": 1.0}) == 0.0
    assert weighted_tag_overlap({}, {}) == 0.0


def test_tag_overlap_weighted_partial():
    # inter = min(ramp)=1.0 (+0 for lifegain); union = 1.0 + 0.5 = 1.5
    assert weighted_tag_overlap(TAGS[1], TAGS[2]) == pytest.approx(1.0 / 1.5)


# --- derive_synergies -------------------------------------------------------

def test_empty_and_singleton_inputs_yield_nothing():
    assert derive_synergies([], TAGS) == []
    solo = [DeckRoster(deck_id=9, format="Standard", card_ids=[1])]
    assert derive_synergies(solo, TAGS) == []


def test_pairs_are_canonically_ordered():
    rows = derive_synergies(DECKS, TAGS)
    assert rows, "fixture should produce pairs"
    for r in rows:
        assert r.card_a_id < r.card_b_id


def test_cooccurrence_and_tag_math():
    rows = by_pair(derive_synergies(DECKS, TAGS))

    # (1,2) Standard: co=2 of union 3 -> jaccard 2/3; shared tag ramp,
    # overlap 1/1.5 = 2/3; score = 0.7*(2/3) + 0.3*(2/3) = 2/3.
    r = rows[("Standard", 1, 2)]
    assert r.co_decks == 2
    assert r.score == pytest.approx(2 / 3, abs=1e-4)
    assert r.confidence == pytest.approx(0.5)
    assert r.synergy_type == SYNERGY_TYPE_SHARED_TAG
    assert r.shared_tags == ["ramp"]
    assert "ramp" in r.reason

    # (3,5) Standard: co=1 of union 2 -> jaccard 0.5; shared removal,
    # overlap 1/2 = 0.5; score 0.5. Confidence from a single deck is low.
    r = rows[("Standard", 3, 5)]
    assert r.co_decks == 1
    assert r.score == pytest.approx(0.5)
    assert r.confidence == pytest.approx(1 / 3, abs=1e-4)
    assert r.synergy_type == SYNERGY_TYPE_SHARED_TAG

    # (1,3) Standard: co-occurs but shares no tags -> co_occurrence type,
    # score is purely the jaccard blend: 0.7 * (1/3).
    r = rows[("Standard", 1, 3)]
    assert r.synergy_type == SYNERGY_TYPE_CO_OCCURRENCE
    assert r.score == pytest.approx(0.7 / 3, abs=1e-4)
    assert r.shared_tags == []


def test_formats_never_mix_evidence():
    rows = by_pair(derive_synergies(DECKS, TAGS))
    # (1,4) only co-occurs in the Historic deck.
    assert ("Historic", 1, 4) in rows
    assert ("Standard", 1, 4) not in rows
    historic = rows[("Historic", 1, 4)]
    assert historic.format == "Historic"
    assert historic.co_decks == 1
    # jaccard 1.0 (both cards appear in exactly that one deck), no tags.
    assert historic.score == pytest.approx(0.7)


def test_duplicate_cards_within_a_deck_collapse():
    dup = [DeckRoster(deck_id=1, format="Standard", card_ids=[1, 1, 2, 2])]
    rows = derive_synergies(dup, TAGS)
    assert len(rows) == 1
    assert rows[0].co_decks == 1


def test_min_co_decks_threshold():
    rows = derive_synergies(DECKS, TAGS, min_co_decks=2)
    pairs = {(r.format, r.card_a_id, r.card_b_id) for r in rows}
    assert pairs == {("Standard", 1, 2), ("Standard", 2, 3)}


# --- build_synergy_row ------------------------------------------------------

def test_build_synergy_row_maps_fields():
    from apps.api.derive_synergies import build_synergy_row
    from apps.api.synergy_derivation import DerivedSynergy

    d = DerivedSynergy(
        card_a_id=1,
        card_b_id=2,
        synergy_type=SYNERGY_TYPE_SHARED_TAG,
        score=0.6667,
        confidence=0.5,
        reason="fixture",
        format="Standard",
        co_decks=2,
        shared_tags=["ramp"],
    )
    row = build_synergy_row(d)
    assert row.card_a_id == 1 and row.card_b_id == 2
    assert row.synergy_type == SYNERGY_TYPE_SHARED_TAG
    assert row.score == 0.6667 and row.confidence == 0.5
    assert row.reason == "fixture" and row.format == "Standard"
