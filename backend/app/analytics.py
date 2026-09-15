import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .db import get_db
from .models import MatchHistory
from .schemas import (
    AnalyticsOverviewResponse,
    DeckPerformance,
    MatchupPerformance,
    MatchupsResponse,
    PlayDrawPerformance,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def deck_label(deck: Any) -> str:
    """Return a stable display key without inspecting raw parser payload."""
    if isinstance(deck, str):
        return deck
    if isinstance(deck, dict):
        for key in ("name", "deck_name", "deckName", "deck_id", "deckId", "id"):
            value = deck.get(key)
            if value is not None:
                return str(value)
    return json.dumps(deck, sort_keys=True, separators=(",", ":"), default=str)


def _winrate(wins: int, losses: int) -> float:
    decisive_matches = wins + losses
    return wins / decisive_matches if decisive_matches else 0.0


def _performance(values: dict[str, int]) -> PlayDrawPerformance:
    return PlayDrawPerformance(
        **values,
        winrate=_winrate(values["wins"], values["losses"]),
    )


def build_matchups(
    rows: list[tuple[Any, Any, Any, Any, Any]], my_deck: str | None = None
) -> MatchupsResponse:
    """Aggregate opponent matchups from normalized fields only."""
    filter_label = my_deck.strip() if isinstance(my_deck, str) else None
    if not filter_label:
        filter_label = None
    grouped: dict[str, dict[str, Any]] = {}
    for _, row_my_deck, opponent_deck, match_result, on_play in rows:
        if filter_label and deck_label(row_my_deck) != filter_label:
            continue
        opponent_label = deck_label(opponent_deck)
        summary = grouped.setdefault(
            opponent_label,
            {
                "matches": 0,
                "wins": 0,
                "losses": 0,
                "on_play": {"matches": 0, "wins": 0, "losses": 0},
                "on_draw": {"matches": 0, "wins": 0, "losses": 0},
            },
        )
        result = match_result.strip().lower() if isinstance(match_result, str) else None
        side = "on_play" if on_play else "on_draw"
        stats = summary[side]
        summary["matches"] += 1
        stats["matches"] += 1
        if result == "win":
            summary["wins"] += 1
            stats["wins"] += 1
        elif result == "loss":
            summary["losses"] += 1
            stats["losses"] += 1

    matchups = []
    for opponent_label, summary in sorted(
        grouped.items(),
        key=lambda item: (
            -(item[1]["wins"] + item[1]["losses"]),
            item[0],
        ),
    ):
        matchups.append(
            MatchupPerformance(
                opponent_deck=opponent_label,
                matches=summary["matches"],
                wins=summary["wins"],
                losses=summary["losses"],
                rated_matches=summary["wins"] + summary["losses"],
                winrate=_winrate(summary["wins"], summary["losses"]),
                on_play=_performance(summary["on_play"]),
                on_draw=_performance(summary["on_draw"]),
            )
        )
    return MatchupsResponse(
        deck=filter_label,
        total_matchups=len(matchups),
        matchups=matchups,
    )


def build_overview(rows: list[tuple[Any, Any, Any]]) -> AnalyticsOverviewResponse:
    """Aggregate normalized query rows; draws and null results are non-decisive."""
    total_matches = len(rows)
    wins = 0
    losses = 0
    decks: dict[str, dict[str, int]] = defaultdict(
        lambda: {"matches": 0, "wins": 0, "losses": 0}
    )

    for _, my_deck, match_result in rows:
        result = match_result.strip().lower() if isinstance(match_result, str) else None
        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1

        label = deck_label(my_deck)
        summary = decks[label]
        summary["matches"] += 1
        if result == "win":
            summary["wins"] += 1
        elif result == "loss":
            summary["losses"] += 1

    performance = [
        DeckPerformance(
            deck=label,
            matches=summary["matches"],
            wins=summary["wins"],
            losses=summary["losses"],
            winrate=_winrate(summary["wins"], summary["losses"]),
        )
        for label, summary in sorted(decks.items())
    ]
    favorite_deck = (
        sorted(performance, key=lambda item: (-item.matches, item.deck))[0].deck
        if performance
        else None
    )
    best_deck = (
        sorted(
            performance,
            key=lambda item: (-item.winrate, -item.matches, item.deck),
        )[0].deck
        if performance
        else None
    )
    return AnalyticsOverviewResponse(
        total_matches=total_matches,
        rated_matches=wins + losses,
        overall_winrate=_winrate(wins, losses),
        favorite_deck=favorite_deck,
        best_deck=best_deck,
        deck_performance=performance,
    )


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_overview(db: Session = Depends(get_db)) -> AnalyticsOverviewResponse:
    rows = db.query(
        MatchHistory.match_id,
        MatchHistory.my_deck,
        MatchHistory.match_result,
    ).all()
    return build_overview(rows)


@router.get("/matchups", response_model=MatchupsResponse)
def get_matchups(
    my_deck: str | None = None, db: Session = Depends(get_db)
) -> MatchupsResponse:
    query = db.query(
        MatchHistory.match_id,
        MatchHistory.my_deck,
        MatchHistory.opponent_deck,
        MatchHistory.match_result,
        MatchHistory.on_play,
    )
    rows = query.all()
    return build_matchups(rows, my_deck)
