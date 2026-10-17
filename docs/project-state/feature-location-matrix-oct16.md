# Arena Helper — Feature × Location Matrix (Oct 16, 2026)

Verified from: production live gates, GitHub read-backs, the local-vs-stable tree diff,
Neon/engine row counts, and fixture/simulation tests run Oct 16. Legend: **LIVE** = running
in production · ✓ = present & verified · ◐ = present, partial/unproven · ✗ = absent ·
— = not applicable.

| Feature | Local snapshot (34924a3) | render-dev (28b945c) | stable/importer-fix (a62aa6c) | Render production | Render dev service |
|---|---|---|---|---|---|
| Recommendations (decks) | ✓ | ✓ | ✓ | **LIVE** | not stood up |
| Next-action (fixed B3 bridge) | ◐ older differing version | ✓ | ✓ | **LIVE** (Ledger Shredder verified) | not stood up |
| Auth / users | ✓ | ✓ | ✓ | **LIVE** | not stood up |
| Deck Lab UI + consent submissions | ✗ | ✓ v3 | ✓ v1 | **LIVE** v1 (submission #1 stored in Neon) | not stood up |
| Collection analysis (browser) | ✗ | ✓ | ✓ v1 | **LIVE** v1 | not stood up |
| With/without-wildcard board split | ✗ | ✓ | ✗ | ✗ | not stood up |
| DB-true rarities endpoint | ✗ | ✓ | ✗ | ✗ | not stood up |
| Meta library (8 Standard decks) | ✗ | ✓ | ✗ | ✗ | not stood up |
| Winners library (7 first-place lists) | ✗ | ✓ | ✗ | ✗ | not stood up |
| Legality engine + breakdowns | ✗ | ✓ | ✗ | ✗ | not stood up |
| Local intel scripts (brain_lab etc., 15 tools) | ✓ | ✓ | ✗ | ✗ | not stood up |
| Card database (38,906 cards / 118,527 prints) | ◐ local Postgres | ✓ via Neon | ✓ via Neon | **LIVE** (Neon) | needs Neon dev branch |
| card_tags (13,458) | ◐ | ✓ | ✓ | **LIVE** (Neon) | needs Neon dev branch |
| Collection rows (Neon user_collections 12,960) | ◐ | ✓ | ✓ | **LIVE** | branch copy when created |
| Engine graph (engines 2 / user_collection 4,766) | ✓ | ✓ | ✓ | **LIVE** (SQLite side) | deploys with service |
| ~90 local decks (Oct 12 triage) | ✓ local Postgres ONLY | ✗ | ✗ | ✗ | ✗ — needs pg_dump export from Billy |
| Match ingestion | ◐ fragments unaudited | ◐ same | ◐ same | ✗ not wired (match_histories 0) | ✗ |
| Telemetry | ◐ tables exist | ◐ tables exist | ◐ tables exist | ✗ 0 rows | ✗ |
| card_synergies | ◐ table exists | ◐ | ◐ | ✗ 0 rows | ✗ |
| Meta stats (meta_card_stats) | ◐ | ◐ 45 rows | ◐ 45 rows | ◐ partial | ◐ |

## Local disk ground truth (Billy's terminal output, Oct 16 ~19:52)

- Directory inventory matches the repo audit, plus: `apps/api/services/`, `apps/api/core/`,
  `apps/api/MatchReports/Active/`, and the backup folder
  `apps/api/backup_20260921_164336_handoff/` all confirmed on disk.
- Databases on disk: root `engine_graph.db` 532,480 B; `apps/api/engine_graph.db` 528,384 B
  (+ identical-size backup copy); root `arena_helper.db` 303,104 B (the staging DB — real);
  `backend/arena_helper.db` only 16,384 B (near-empty). Plus 16 mypy cache DBs (noise).
- `services/` on disk has ONE file (recommendation_service.py, Oct 6) — the snapshot predates
  the other three services that live on stable/render-dev. Expected, not corruption.
- LOCAL-ONLY branches never pushed to GitHub: feature/postgres-migration-and-cleanup,
  recovery-merge-snapshot, review-telemetry, review-website, sandbox/auth-consolidation,
  sandbox/collection-engine, sandbox/database-recovery, stable/safe-recovery.
- Match wiring: root `main.py` (Platform A) imports and wires matches + router_match;
  the production `apps/api/main.py` lineage does NOT wire them — match routers are files,
  not features, in production.
- An other-AI `python -c` patch to root recommendations.py (hardcoded BRAIN_LAB_SCORES
  scoring) FAILED with SyntaxError before writing — file unchanged, nothing applied.

## What this matrix says

1. **Nothing exists only in production.** Everything live is in git; render-dev is a
   strict superset of stable plus the local-only tooling.
2. **The only data living in exactly one place** is Billy's ~90 local decks (local
   Postgres) — one pg_dump export away from being portable.
3. **The dev service column is empty for one reason only:** the two dashboard steps
   (Neon dev branch + Render service pointing at render-dev). The code is ready.
4. **Phase 2 is the bottom three rows** — match ingestion, telemetry, synergies:
   schema and fragments exist everywhere; data and wiring exist nowhere.
