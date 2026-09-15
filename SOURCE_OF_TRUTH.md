# Arena Helper — Source of Truth

## Metadata & Parsing Authority
* **Cards, Sets, & Formats:** Generator (Pipeline A) — Generates standalone reference data artifacts.

## Application & Runtime Authority
* **Users, Collections, Decks, & Match History:** PostgreSQL ORM / FastAPI (Pipeline B).
* **Schema Authority:** Alembic migrations (pps/api/alembic).
* **Runtime Authority:** FastAPI database session management (pps/api/database.py).
