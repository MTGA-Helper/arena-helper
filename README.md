# Arena Helper

Arena Helper is a foundation for collecting MTG Arena match telemetry, retaining
parser-specific data, and producing normalized analytics and recommendations.
The current backend exposes telemetry ingestion and read-only analytics APIs.

## Architecture

The intended flow is:

```text
collection -> recommendations -> telemetry -> MatchHistory -> analytics
```

See [docs/architecture.md](docs/architecture.md) for boundaries and data flow.

## Setup

Requirements: Python 3.10 or newer.

```powershell
python -m pip install -e '.[test]'
$env:PYTHONPATH = "backend"
```

The default database is SQLite at `./arena_helper.db`. Set `DATABASE_URL` to use
another SQLAlchemy-compatible database:

```powershell
$env:DATABASE_URL = "sqlite:///./arena_helper.db"
```

Importing `app.main` creates the declared schema with
`Base.metadata.create_all`. There is currently no migration tooling, so this is
appropriate only for the current foundation and development workflows.

`uvicorn` is not declared in `pyproject.toml`; install it separately before
starting the API:

```powershell
python -m pip install uvicorn
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## API

- `POST /matches/ingest` accepts the normalized MatchTelemetryV1 fields and
  keeps every additional parser field in `raw_payload`.
- `GET /analytics/overview` summarizes all normalized match rows.
- `GET /analytics/matchups?my_deck=...` summarizes normalized opponent matchups.

Examples and limitations are documented in
[docs/telemetry.md](docs/telemetry.md) and
[docs/analytics.md](docs/analytics.md).

## Tests

```powershell
python -m pytest backend/tests
```

The test dependencies are optional. In restricted environments, dependency
installation or runtime tests may be unavailable; `python -m compileall -q
backend` is a dependency-light syntax check.

## Branch and release status

Work is developed on `telemetry-integration`; `main` remains the foundation
baseline. See [docs/releases.md](docs/releases.md) for the exact current
commit/tag state and the local-only analytics milestone.
