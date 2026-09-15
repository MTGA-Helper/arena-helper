# Telemetry

## MatchTelemetryV1

`POST /matches/ingest` requires these normalized fields:

```json
{
  "match_id": "match-123",
  "timestamp": "2026-09-15T14:00:00Z",
  "my_deck": {"name": "Mono Red"},
  "opponent_deck": {"name": "Control"},
  "opponent_colors": ["U", "W"],
  "match_result": "win",
  "event_id": "event-123",
  "opponent_platform": "arena",
  "on_play": true
}
```

The endpoint returns HTTP 201 on success. `match_id` is unique; a duplicate
returns HTTP 409. Missing or invalid required fields are rejected by FastAPI
and Pydantic with HTTP 422.

## Raw payload behavior

Every field not in the normalized contract is retained in `raw_payload`. This
includes parser output such as GameActions, TurnSnapshots, GameSnapshots,
DeckMaps, ParseStats, and fields such as `imported_at`.

The bridge recursively serializes parser values into JSON-compatible data:
Mappings become sorted-key objects, Sets and frozensets become deterministically
sorted arrays, dates become ISO strings, and nested sequences/value objects are
converted recursively. Analytics does not use this payload.

## Example response

```json
{
  "id": 1,
  "match_id": "match-123",
  "timestamp": "2026-09-15T14:00:00+00:00",
  "my_deck": {"name": "Mono Red"},
  "opponent_deck": {"name": "Control"},
  "opponent_colors": ["U", "W"],
  "match_result": "win",
  "event_id": "event-123",
  "opponent_platform": "arena",
  "on_play": true,
  "raw_payload": {"parserVersion": "4.x"}
}
```

## Limitations

The parser npm package is not imported at application import time. The bridge
accepts parser objects or JSON-compatible values, so the API can run without
that package installed. The repository does not currently provide a collector,
background ingestion worker, authentication, or database migration tooling.
