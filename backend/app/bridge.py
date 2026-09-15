"""Adapter from mtga-log-parser output to API persistence models.

The parser is intentionally not imported here. Applications can pass parser
objects or JSON-compatible dictionaries, allowing the API to run without the
npm package installed.
"""

from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from typing import Any

from .schemas import (
    ActionCreate,
    CardCreate,
    DeckCreate,
    DrawCreate,
    GameCreate,
    MatchCreate,
    TurnCreate,
)


def json_safe(value: Any) -> Any:
    """Convert parser Maps, Sets, dates, and value objects to JSON-safe data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return json_safe(value.value)
    if isinstance(value, Mapping):
        return {
            str(json_safe(key)): json_safe(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (set, frozenset)):
        return [json_safe(item) for item in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "items") and callable(value.items):
        return {
            str(json_safe(key)): json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if hasattr(value, "toJSON") and callable(value.toJSON):
        return json_safe(value.toJSON())
    if hasattr(value, "__dict__"):
        return {
            str(key): json_safe(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    raise TypeError(f"Unsupported telemetry value: {type(value).__name__}")


NORMALIZED_TELEMETRY_FIELDS = frozenset({
    "match_id",
    "timestamp",
    "my_deck",
    "opponent_deck",
    "opponent_colors",
    "match_result",
    "event_id",
    "on_play",
    "opponent_platform",
})


def split_telemetry_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = {
        key: (
            payload[key] if key == "timestamp" else json_safe(payload[key])
        )
        for key in NORMALIZED_TELEMETRY_FIELDS
        if key in payload
    }
    extras = {key: value for key, value in payload.items() if key not in NORMALIZED_TELEMETRY_FIELDS}
    return json_safe(normalized), json_safe(extras)


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def map_parser_match(source: Any) -> MatchCreate:
    games = [
        map_parser_game(game)
        for game in (_get(source, "games", _get(source, "gameSnapshots", [])) or [])
    ]
    return MatchCreate(
        match_id=str(_get(source, "match_id", _get(source, "matchId", ""))),
        player_id=_get(source, "player_id", _get(source, "playerId")),
        opponent_id=_get(source, "opponent_id", _get(source, "opponentId")),
        started_at=_get(source, "started_at", _get(source, "startedAt")),
        ended_at=_get(source, "ended_at", _get(source, "endedAt")),
        result=_get(source, "result"),
        raw_metadata=dict(_get(source, "raw_metadata", _get(source, "metadata", {})) or {}),
        games=games,
    )


def map_parser_game(source: Any) -> GameCreate:
    turns = [
        map_parser_turn(turn)
        for turn in (_get(source, "turns", _get(source, "turnSnapshots", [])) or [])
    ]
    return GameCreate(
        game_number=int(_get(source, "game_number", _get(source, "gameNumber", 0))),
        player_life=_get(source, "player_life", _get(source, "playerLife")),
        opponent_life=_get(source, "opponent_life", _get(source, "opponentLife")),
        active_player=_get(source, "active_player", _get(source, "activePlayer")),
        raw_data=dict(_get(source, "raw_data", _get(source, "raw", {})) or {}),
        turns=turns,
    )


def map_parser_turn(source: Any) -> TurnCreate:
    draws = [
        DrawCreate(
            card_name=str(_get(draw, "card_name", _get(draw, "cardName", ""))),
            card_id=_get(draw, "card_id", _get(draw, "cardId")),
            draw_index=int(_get(draw, "draw_index", _get(draw, "index", index))),
        )
        for index, draw in enumerate(_get(source, "draws", _get(source, "drawRecords", [])) or [])
    ]
    actions = [
        ActionCreate(
            action_type=str(_get(action, "action_type", _get(action, "type", ""))),
            player_id=_get(action, "player_id", _get(action, "playerId")),
            card_id=_get(action, "card_id", _get(action, "cardId")),
            payload=dict(_get(action, "payload", {}) or {}),
        )
        for action in (_get(source, "actions", _get(source, "gameActions", [])) or [])
    ]
    return TurnCreate(
        turn_number=int(_get(source, "turn_number", _get(source, "turnNumber", 0))),
        active_player=_get(source, "active_player", _get(source, "activePlayer")),
        raw_data=dict(_get(source, "raw_data", _get(source, "raw", {})) or {}),
        draws=draws,
        actions=actions,
    )


def map_parser_deck(source: Any) -> DeckCreate:
    entries = _get(source, "cards", _get(source, "cardEntries", [])) or []
    return DeckCreate(
        deck_id=str(_get(source, "deck_id", _get(source, "deckId", ""))),
        name=_get(source, "name"),
        format=_get(source, "format"),
        cards=[
            CardCreate(
                card_id=str(_get(card, "card_id", _get(card, "cardId", ""))),
                card_name=str(_get(card, "card_name", _get(card, "cardName", ""))),
                quantity=int(_get(card, "quantity", _get(card, "count", 0))),
            )
            for card in entries
        ],
    )
