# Master Capability Matrix — Arena Helper

**Status:** Active Reconstruction Phase  
**Baseline:** Post-Rebase Clean Dev Environment (dev)  
**Objective:** Track empirical verification, evidence levels, and canonical ownership across Platform, Intelligence, and Portal worlds.

## Capability Truth Table

| Capability / Subsystem | Local Recovery | GitHub (dev / websites-split) | Render Production | Portal Layer (user-portal) | Evidence Level | Canonical Owner | Action Item & Integration Status |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- |
| **Auth / Security** | ⚠️ (Basic) | ✅ (uth-layer) | ⚠️ (Partial) | ✅ (uth.py) | Code Verified | websites-split + uth-layer | **Merge:** Adopt Matt's FastAPI /auth microservice as canonical gateway. |
| **User Model** | ✅ (models.py) | ✅ (models.py) | ✅ | ✅ (models.py) | Code Verified | Intelligence World (models.py) | **Verify:** Unify UUID/String primary key definitions across PostgreSQL & SQLite. |
| **Collection Upload** | ✅ (collection.py) | ❌ | ❌ | ❌ | Code Verified | Intelligence World (collection.py) | **Integrate:** Wire CSV bulk-upsert endpoint (/collection/upload) into active app. |
| **Collection Stats** | ✅ (collection.py) | ❌ | ❌ | ❌ | Code Verified | Intelligence World (collection.py) | **Integrate:** Mount ownership counts, unique card totals, and wildcard balances. |
| **Card / Deck Database**| ✅ (models.py) | ❌ | ❌ | ❌ | Code Verified | Intelligence World (models.py) | **Preserve:** Retain core relational schemas (cards, decks, card_prints). |
| **Deck Analysis** | ✅ (deck_analysis.py) | ❌ | ❌ | ❌ | Code Verified | Intelligence World (deck_analysis.py) | **Recover:** Mount structural scoring loops (Meta, Mana, Synergy, Consistency). |
| **Craft Advisor** | ✅ (craft_priority.py) | ❌ | ❌ | ❌ | Code Verified | Intelligence World (craft_priority.py) | **Recover:** Expose wildcard ROI ranking reports for rare/mythic optimization. |
| **Recommendation Engine**| ✅ (ecommend_engine.py) | ❌ | ❌ | ❌ | Code Verified | Intelligence World (ecommend_engine.py) | **Recover:** Mount personalized deck matching endpoints based on user collection. |
| **Match Tracking / API**| ✅ (matches.py) | ❌ | ❌ | ❌ | Code Verified | Intelligence World (matches.py) | **Recover:** Mount telemetry ingestion (/matches/ingest) and history lookup. |
| **Upgrade Advisor** | ✅ | ✅ (dev) | ✅ (Live) | ❌ | Code Verified + Live | Render / dev | **Preserve:** Keep operational and sync against local SQLite/Postgres schemas. |
| **Telemetry / Health** | ✅ | ✅ (dev) | ✅ (Live) | ✅ (main.py) | Code Verified + Live | Render / dev | **Preserve:** Retain active /health check and telemetry monitoring hooks. |
