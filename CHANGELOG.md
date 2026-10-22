# Arena Helper — Changelog

## 2026-10-21 — PR #17 merged to dev (merge commit 9bf1ae9)
- **What:** mtga-log-parser now preserves draw results, captures post-match rank, and tracks PlayLand actions; log-ingestion pipeline + ELK dashboard scaffolding added; verified duplicate files removed from the working tree. Test suite: 96 vitest tests, all passing at merge (run by maintainer — they had never been executed).
- **Handling change:** the ELK services (setup, es01, kibana, logstash01) are gated behind the `elk` docker-compose profile (commit bcd492f) so a plain `docker compose up` stays light; opt in with `docker compose --profile elk up`.
- **Why:** richer log parsing feeds the deck/match analysis work; the ELK stack is an opt-in observability tool, not a default boot cost on dev machines.
- **Release state:** dev only (BETA track). Production (stable/importer-fix) untouched.
- **Notes:** `collection.csv` and `backend/arena_helper.db` left the working tree in this merge; both are recoverable from commit 6a494b2 (`git show 6a494b2:<path> > <path>`). Making the new enforce-dev-to-main workflow a required status check on main is a follow-up.
