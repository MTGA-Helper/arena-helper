# -*- coding: utf-8 -*-
"""
Synergy derivation — pure functions, no database access.

Derives pairwise card synergy *candidates* for the card_synergies table from
two honest signals that already exist in the data:

  1. Co-occurrence: how often two cards appear together in the same deck,
     measured per format as a Jaccard index over deck rosters.
  2. Tag overlap: how much the two cards' functional tags (card_tags)
     overlap, as a score-weighted Jaccard index over their tag sets.

Nothing here invents synergy knowledge. A pair is emitted only if the two
cards actually co-occur in at least one real deck roster. The resulting
``score`` is a blended statistic on a 0.0-1.0 scale (NOT a percentage and
NOT a judgment of card quality), and ``confidence`` grows with the amount
of co-occurrence evidence, so thin data stays visibly thin:

    confidence = co_decks / (co_decks + 2)     # 1 deck -> 0.33, 4 -> 0.67

The raw evidence (deck counts, shared tags) is preserved on each result and
in the human-readable ``reason`` string, so any future consumer can audit
or recompute from the same numbers.

Inputs are plain data so the logic is unit-testable without a database:

  decks:     iterable of DeckRoster(deck_id, format, card_ids)
  card_tags: mapping card_id -> mapping tag -> weight (CardTag.score)

Output rows use canonical ordering card_a_id < card_b_id to respect the
uq_card_synergy unique constraint, and carry the format of the decks the
evidence came from.
"""
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, Iterable, List, Mapping, Sequence

# synergy_type values written by this derivation. The "derived:" namespace
# marks rows this pipeline owns; the population script only ever replaces
# rows inside this namespace and never touches hand-authored rows.
SYNERGY_TYPE_CO_OCCURRENCE = "derived:co_occurrence"
SYNERGY_TYPE_SHARED_TAG = "derived:shared_tag"

# Blend weights for the score statistic. Co-occurrence is observed behavior
# and dominates; tag overlap is a weaker, static prior.
W_CO_OCCURRENCE = 0.7
W_TAG_OVERLAP = 0.3


@dataclass(frozen=True)
class DeckRoster:
    """One deck's card presence: which distinct cards it plays."""

    deck_id: int
    format: str
    card_ids: Sequence[int]


@dataclass(frozen=True)
class DerivedSynergy:
    """One derived pair, shaped to map 1:1 onto models.CardSynergy."""

    card_a_id: int
    card_b_id: int
    synergy_type: str
    score: float
    confidence: float
    reason: str
    format: str
    # Raw evidence, kept for auditing and tests (not a DB column).
    co_decks: int = 0
    shared_tags: List[str] = field(default_factory=list)


def weighted_tag_overlap(
    tags_a: Mapping[str, float], tags_b: Mapping[str, float]
) -> float:
    """Score-weighted Jaccard overlap of two tag -> weight mappings.

    Returns 0.0 when either side has no tags or the tag sets are disjoint.
    """
    if not tags_a or not tags_b:
        return 0.0
    keys = set(tags_a) | set(tags_b)
    intersection = sum(min(tags_a.get(k, 0.0), tags_b.get(k, 0.0)) for k in keys)
    union = sum(max(tags_a.get(k, 0.0), tags_b.get(k, 0.0)) for k in keys)
    if union <= 0:
        return 0.0
    return intersection / union


def derive_synergies(
    decks: Iterable[DeckRoster],
    card_tags: Mapping[int, Mapping[str, float]],
    min_co_decks: int = 1,
) -> List[DerivedSynergy]:
    """Derive pairwise synergy candidates from deck rosters + card tags.

    A pair is emitted only when the two cards co-occur in at least
    ``min_co_decks`` decks of the same format. Decks with fewer than two
    distinct cards contribute no pairs. Empty input yields empty output.
    """
    # Group rosters by format; synergy evidence never crosses formats.
    by_format: Dict[str, List[DeckRoster]] = {}
    for roster in decks:
        by_format.setdefault(roster.format, []).append(roster)

    results: List[DerivedSynergy] = []

    for fmt in sorted(by_format):
        rosters = by_format[fmt]
        deck_count: Dict[int, int] = {}
        pair_count: Dict[tuple, int] = {}

        for roster in rosters:
            distinct = sorted(set(roster.card_ids))
            for card_id in distinct:
                deck_count[card_id] = deck_count.get(card_id, 0) + 1
            for pair in combinations(distinct, 2):
                pair_count[pair] = pair_count.get(pair, 0) + 1

        for (a, b), co in sorted(pair_count.items()):
            if co < min_co_decks:
                continue
            union_decks = deck_count[a] + deck_count[b] - co
            jaccard = co / union_decks if union_decks else 0.0

            tags_a = card_tags.get(a, {})
            tags_b = card_tags.get(b, {})
            shared = sorted(set(tags_a) & set(tags_b))
            overlap = weighted_tag_overlap(tags_a, tags_b)

            score = round(W_CO_OCCURRENCE * jaccard + W_TAG_OVERLAP * overlap, 4)
            confidence = round(co / (co + 2), 4)

            if shared:
                synergy_type = SYNERGY_TYPE_SHARED_TAG
                reason = (
                    f"Co-occurs in {co} of {union_decks} decks playing either "
                    f"card ({fmt}); shared tags: {', '.join(shared)}"
                )
            else:
                synergy_type = SYNERGY_TYPE_CO_OCCURRENCE
                reason = (
                    f"Co-occurs in {co} of {union_decks} decks playing either "
                    f"card ({fmt}); no shared tags"
                )

            results.append(
                DerivedSynergy(
                    card_a_id=a,
                    card_b_id=b,
                    synergy_type=synergy_type,
                    score=score,
                    confidence=confidence,
                    reason=reason,
                    format=fmt,
                    co_decks=co,
                    shared_tags=shared,
                )
            )

    results.sort(key=lambda r: (r.format, -r.score, r.card_a_id, r.card_b_id))
    return results
