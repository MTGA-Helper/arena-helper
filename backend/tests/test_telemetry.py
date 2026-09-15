from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.bridge import json_safe, split_telemetry_payload
from app.db import Base
from app.main import app
from app.models import MatchHistory
from app.schemas import MatchTelemetryV1


NORMALIZED_FIELDS = {
    "match_id",
    "timestamp",
    "my_deck",
    "opponent_deck",
    "opponent_colors",
    "match_result",
    "event_id",
    "on_play",
    "opponent_platform",
}


def valid_payload() -> dict:
    return {
        "match_id": "m-1",
        "timestamp": "2026-09-14T20:00:00Z",
        "my_deck": {"main": ["Island"]},
        "opponent_deck": {"main": ["Mountain"]},
        "opponent_colors": ["R"],
        "match_result": "win",
        "event_id": "event-1",
        "on_play": True,
        "opponent_platform": "arena",
    }


def test_v1_model_has_exact_normalized_fields():
    assert set(MatchTelemetryV1.__fields__) == NORMALIZED_FIELDS
    assert set(MatchHistory.__table__.columns.keys()) == NORMALIZED_FIELDS | {
        "id",
        "created_at",
        "raw_payload",
    }


def test_ingest_returns_201_and_retains_parser_extras():
    client = TestClient(app)
    payload = {
        **valid_payload(),
        "imported_at": "2026-09-14T20:01:00Z",
        "GameActions": {"draws": {"Island", "Mountain"}},
        "TurnSnapshots": [{"turnNumber": 1}],
        "ParseStats": {"cards": 2},
    }
    response = client.post("/matches/ingest", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["match_id"] == "m-1"
    assert body["raw_payload"]["imported_at"] == "2026-09-14T20:01:00Z"
    assert body["raw_payload"]["GameActions"]["draws"] == ["Island", "Mountain"]
    assert body["raw_payload"]["ParseStats"] == {"cards": 2}


def test_ingest_requires_all_normalized_fields():
    client = TestClient(app)
    response = client.post("/matches/ingest", json={"match_id": "incomplete"})
    assert response.status_code == 422


def test_split_and_json_safe_are_deterministic_for_maps_sets_and_dates():
    normalized, extras = split_telemetry_payload({
        **valid_payload(),
        "imported_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "DeckMaps": {"sideboard": {"Mountain", "Island"}},
    })
    assert set(normalized) == NORMALIZED_FIELDS
    assert "imported_at" in extras
    assert extras["DeckMaps"]["sideboard"] == ["Island", "Mountain"]
    assert json_safe({"values": {2, 1}}) == {"values": [1, 2]}


def test_parser_entity_names_have_no_sqlalchemy_tables():
    table_names = set(Base.metadata.tables)
    assert not table_names.intersection({
        "game_actions",
        "turn_snapshots",
        "game_snapshots",
        "deck_maps",
        "parse_stats",
    })
