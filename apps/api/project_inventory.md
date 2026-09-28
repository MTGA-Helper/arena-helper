# Project Inventory (Arena Helper Platform)

## 1. Folder Tree & Architecture
- `apps/api/` - FastAPI backend, modular routers (`collection.py`, `matches.py`, `recommendations.py`, `router_match.py`), core `main.py`, models, and database engine configurations.
- `database/` - Centralized repository for all SQLite databases, SQL dumps, models, and migration scripts.

## 2. Backend Files
- `main.py` - FastAPI application root with lifespan checks and router inclusions.
- `database.py` - SQLAlchemy async session maker and engine configurations.
- `models.py` - ORM models (`User`, `UserCollection`, `Card`, `Deck`, `MatchHistory`, etc.).
- `collection.py` - CSV collection import endpoint.
- `matches.py` & `router_match.py` - Match ingestion and telemetry routers.
- `recommendations.py` - Deck crafting and upgrade recommendations engine.

## 3. Infrastructure & Deployment Files
- `Dockerfile` - Container definition for FastAPI backend.
- `docker-compose.yml` - Multi-service local stack orchestration.
- `requirements.txt` - Python backend dependencies.

## 4. Notes for Matt / Developer Review
- Original files remain completely untouched and secure in `C:\Users\siniz\arena-helper`.
- All database artifacts, models, and configuration files are fully mirrored under the target folder for review.
- Ready for Sprint 1 integration and user authentication rollout.