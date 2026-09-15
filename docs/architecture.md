# Architecture

## Current flow

Arena Helper is organized around this conceptual flow:

```text
collection -> recommendations -> telemetry -> MatchHistory -> analytics
```

- **Collection** receives match data from an external collector or
  `mtga-log-parser` adapter.
- **Recommendations** is the intended consumer-facing decision layer; no
  recommendation endpoint is currently implemented in this repository.
- **Telemetry** validates MatchTelemetryV1 and accepts parser output.
- **MatchHistory** stores the ten normalized match values required by the
  telemetry contract plus the lossless `raw_payload`.
- **Analytics** reads normalized MatchHistory columns only. It never reads
  `raw_payload`.

## Backend layout

- `backend/app/main.py` creates the FastAPI app, initializes the current schema,
  and registers routes.
- `backend/app/telemetry.py` implements ingestion.
- `backend/app/analytics.py` implements overview and matchup aggregation.
- `backend/app/models.py` defines the `match_history` SQLAlchemy table.
- `backend/app/schemas.py` defines Pydantic request and response contracts.
- `backend/app/bridge.py` separates normalized parser fields from extras and
  converts Maps, Sets, dates, and nested values to JSON-safe structures.

There are no separate SQLAlchemy tables for GameActions, TurnSnapshots,
GameSnapshots, DeckMaps, or ParseStats. Those parser structures remain in
`raw_payload`.

## Persistence lifecycle

`app.main` calls `Base.metadata.create_all(bind=engine)` during import. The
default database URL is `sqlite:///./arena_helper.db`; `DATABASE_URL` overrides
it. No Alembic or other migration system exists yet. Production schema changes
therefore require a migration strategy before deployment.
