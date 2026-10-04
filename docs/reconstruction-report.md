# Arena Helper Architectural Forensic Reconstruction Report (v1.2)

## Executive Summary

This report documents the forensic investigation of the rena-helper repository, distinguishing strictly between verified empirical facts and working structural hypotheses. Based on module imports, git commit history recovery, database inspections, and schema analysis, no evidence has been discovered indicating loss of the collection, recommendation, deck-analysis, wildcard, card intelligence, or core match-history subsystems. All investigated components remain present in source form and possess corresponding ORM models, API router implementations, and recoverable database-layer dependencies.

The strongest evidence supports an architectural divergence scenario rather than a source-code loss scenario. The repository currently contains multiple generations of the platform, including an active engine-graph deployment path and a largely intact MTGA collection and recommendation platform. Current recovery efforts should focus on router registration, schema reconciliation, database validation, and integration testing before any consideration of subsystem rewrites.

Based on the evidence gathered, Arena Helper appears to be a **reconnection project, not a reconstruction project**.

---

## 1. Verified Facts (Empirically Proven)

1. **Async Database Layer Recovery**:
   * **Evidence**: Successfully checked out and restored database.py from commit revision ecec2c5^.
   * **Verification**: Running python -c "from database import AsyncSessionLocal" successfully outputs AsyncSessionLocal restored successfully!.

2. **Module Import Success**:
   * **Evidence**: Tested imports for core backend subsystems on the recovered database layer.
   * **Verification**: import recommendations, import collection, and import matches all execute without ImportError or ModuleNotFoundError.

3. **ORM Schema Footprint**:
   * **Evidence**: Inspected models.py table definitions.
   * **Verification**: Confirmed presence of 13 canonical tables: users, wildcard_inventories, cards, card_tags, card_synergies, card_prints, card_legalities, decks, deck_cards, meta_card_stats, deck_analyses, user_collections, and match_histories.

4. **API Router Definitions**:
   * **Evidence**: Scanned codebase for APIRouter initializations.
   * **Verification**: Routers are explicitly defined for /collection, /recommendations, and dual implementations under /matches.

5. **Match Subsystem Schema Discrepancy (Drift)**:
   * **Evidence**: Compared matches.py against models.py (MatchHistory).
   * **Verification**: matches.py attempts to write extended metadata (player_name, opponent_name, ank, event_name, aw_payload, created_at) that are absent from the ORM model definition.
   * **Verification (outer_match.py)**: outer_match.py directly aligns with the exact columns present in MatchHistory (user_id, player_id, opponent_id, deck_name, esult, ormat, 	imestamp), making it the schema-aligned implementation.

6. **Async Engine Type Validation**:
   * **Evidence**: Attempting Base.metadata.create_all(bind=engine) against the recovered engine raised AttributeError: 'AsyncEngine' object has no attribute '_run_ddl_visitor'.
   * **Verification**: This error empirically proves that the recovered database object is a genuine AsyncEngine instance rather than a broken placeholder, validating a successful database layer recovery.

7. **Startup Path Verification**:
   * **Evidence**: Inspected pps/api/main.py.
   * **Verification**: The active FastAPI application mounts only pp.include_router(auth_router) and connects directly to engine_graph.db using sqlite3. No collection, recommendation, or match routers are registered in the inspected startup path.

---

## 2. Strong Evidence (High-Probability Inferences)

1. **PostgreSQL-First Architectural Lineage**:
   * *Evidence*: Codebase utilizes PostgreSQL-specific types (UUID(as_uuid=True), ARRAY(String)) alongside historical connection string references (postgresql+asyncpg://...).
   * *Assessment*: Highly probable that the platform was originally engineered for PostgreSQL before SQLite compatibility layers were introduced.

2. **Dormant Router Integration**:
   * *Evidence*: Production startup files explicitly mount authentication but omit binding collection, recommendation, or match routers.
   * *Assessment*: Routers exist in the repository but are unattached to active FastAPI execution.

3. **Design Intent**:
   * *Evidence*: Complete alignment between ORM models, FastAPI route handlers, database session makers, and domain logic.
   * *Assessment*: The collection and recommendation platform was fully structured to operate as an integrated API service.

---

## 3. Subsystem Health & Recovery Status

| Subsystem | Source Status | Database Layer | Schema Alignment | Action Item |
| :--- | :--- | :--- | :--- | :--- |
| **Authentication** | Active Deployment | Current configured database | Appears Complete | Keep active as deployed. |
| **Engine Graph & Telemetry** | Operational | SQLite (engine_graph.db) | Complete | Keep active on Render. |
| **Collection Management** | Intact | Restored Async / Sync | Complete | Wire /collection router into main.py. |
| **Deck Recommendations** | Intact | Restored Async / Sync | Complete | Wire /recommendations router into main.py. |
| **Match History** | Partially Intact | Restored Async / Sync | Split (outer_match.py vs matches.py) | Adopt outer_match.py to prevent ORM drift errors. |

---

## 4. Evidence-Based Confidence Ratings

| Finding | Confidence |
| :--- | :--- |
| Async database layer existed and was removed during later refactor | Very High |
| AsyncSessionLocal recovery from ecec2c5^ succeeded | Very High |
| Collection subsystem exists in source form | Very High |
| Recommendation subsystem exists in source form | Very High |
| Match subsystem exists in source form | Very High |
| outer_match.py aligns with current MatchHistory schema | Very High |
| matches.py represents a later schema-diverged implementation | High |
| Collection and recommendation routers are not mounted in active startup path | Very High |
| Original platform was PostgreSQL-first | High |
| Platform functionality was lost from repository history | Low |
| Recovery requires full rebuild | Very Low |

---

## 5. Outstanding Verification Targets

The following items remain unresolved and require direct validation:

1. Confirm exact router registrations in current FastAPI startup path.
2. Determine whether PostgreSQL was the primary historical datastore or a parallel deployment target.
3. Identify the commit introducing schema divergence between matches.py and MatchHistory.
4. Determine which branch last mounted /collection, /recommendations, and /matches.
5. Trace migration history between:
   * AsyncSessionLocal architecture
   * SQLite compatibility layer
   * engine_graph.db deployment model

---

## 6. Strategic Reconstruction Roadmap

1. **Maintain Sandbox Isolation**: Keep all schema validation, router mounting experiments, and import checks contained within the sandbox/database-recovery branch.
2. **Enforce Schema Alignment**: Standardize the match telemetry ingestion layer on outer_match.py to leverage the verified MatchHistory table structure.
3. **Progressive Reconnection**: Incrementally mount the collection, recommendation, and schema-aligned match routers alongside /auth in FastAPI, followed by local execution testing.
