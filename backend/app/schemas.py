from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, validator


class TelemetryBase(BaseModel):
    class Config:
        orm_mode = True


class DrawCreate(TelemetryBase):
    card_name: str = Field(min_length=1, max_length=256)
    card_id: str | None = None
    draw_index: int = Field(ge=0)


class ActionCreate(TelemetryBase):
    action_type: str = Field(min_length=1, max_length=64)
    player_id: str | None = None
    card_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TurnCreate(TelemetryBase):
    turn_number: int = Field(ge=0)
    active_player: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    draws: list[DrawCreate] = Field(default_factory=list)
    actions: list[ActionCreate] = Field(default_factory=list)


class GameCreate(TelemetryBase):
    game_number: int = Field(ge=0)
    player_life: int | None = None
    opponent_life: int | None = None
    active_player: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    turns: list[TurnCreate] = Field(default_factory=list)


class MatchCreate(TelemetryBase):
    match_id: str = Field(min_length=1, max_length=128)
    player_id: str | None = None
    opponent_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    result: str | None = Field(default=None, max_length=32)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    games: list[GameCreate] = Field(default_factory=list)

    @validator("ended_at")
    def end_after_start(cls, value: datetime | None, values: dict[str, Any]) -> datetime | None:
        started = values.get("started_at")
        if value is not None and started is not None and value < started:
            raise ValueError("ended_at must be after started_at")
        return value


class MatchIngestRequest(TelemetryBase):
    """mtga-log-parser v1 normalized fields; parser extras remain in raw_payload."""

    match_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    my_deck: dict[str, Any] | list[Any]
    opponent_deck: dict[str, Any] | list[Any]
    opponent_colors: list[Any]
    match_result: str = Field(min_length=1, max_length=32)
    event_id: str = Field(min_length=1, max_length=128)
    opponent_platform: str = Field(min_length=1, max_length=64)
    on_play: bool
    class Config(TelemetryBase.Config):
        extra = "allow"
        smart_union = True


class MatchTelemetryV1(MatchIngestRequest):
    """Public name for the v1 telemetry request/response contract."""


class MatchIngestResponse(MatchTelemetryV1):
    id: int
    raw_payload: dict[str, Any]


class DeckPerformance(TelemetryBase):
    deck: str
    matches: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    winrate: float = Field(ge=0.0, le=1.0)


class AnalyticsOverviewResponse(TelemetryBase):
    total_matches: int = Field(ge=0)
    rated_matches: int = Field(ge=0)
    overall_winrate: float = Field(ge=0.0, le=1.0)
    favorite_deck: str | None = None
    best_deck: str | None = None
    deck_performance: list[DeckPerformance] = Field(default_factory=list)


class PlayDrawPerformance(TelemetryBase):
    matches: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    winrate: float = Field(ge=0.0, le=1.0)


class MatchupPerformance(TelemetryBase):
    opponent_deck: str
    matches: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    rated_matches: int = Field(ge=0)
    winrate: float = Field(ge=0.0, le=1.0)
    on_play: PlayDrawPerformance
    on_draw: PlayDrawPerformance


class MatchupsResponse(TelemetryBase):
    deck: str | None = None
    total_matchups: int = Field(ge=0)
    matchups: list[MatchupPerformance] = Field(default_factory=list)


class CardCreate(TelemetryBase):
    card_id: str = Field(min_length=1, max_length=128)
    card_name: str = Field(min_length=1, max_length=256)
    quantity: int = Field(gt=0)


class DeckCreate(TelemetryBase):
    deck_id: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, max_length=256)
    format: str | None = Field(default=None, max_length=64)
    cards: list[CardCreate] = Field(default_factory=list)
