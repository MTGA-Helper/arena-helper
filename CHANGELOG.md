# Arena Helper — Changelog

## 2026-10-21 — ARENA-4 security fix: JWT secret out of source, into env (PR #18; dev merge e29d4d0)
- **What:** The API signed JWTs with the hardcoded placeholder `"super-secret-key-change-me"` in this public repo (`apps/api/auth.py`), and the token verifier (`apps/api/security.py`) defaulted to the same string. Both now read `SECRET_KEY` from the environment and **refuse to boot** without a real one. A real generated secret is set on both Render services. All previously issued tokens are invalid — users log in fresh.
- **Also fixed:** the register endpoint printed the database bind URL (credentials embedded) to stdout on every signup; the diagnostics/exception prints are removed.
- **Why:** audit AU-1 (Oct 21 code audit). Anyone could have minted a valid token for any account the moment a route trusts these tokens; the log print was leaking live DB credentials into Render logs on every registration.
- **Verified on dev before promotion:** service boots on the env secret (fail-fast guard active in both modules); register/login round-trip passes (201/200). Note: no mounted route verifies JWTs yet (collection/recommendations use stub user ids; matches use an ingest-token header) — wiring `security.get_current_user` in is tracked as audit follow-up AU-1b, before any route relies on auth.
- **Release state:** dev + production (stable/importer-fix) — security fix, promoted same night with owner approval.

## 2026-10-21 — PR #17 merged to dev (merge commit 9bf1ae9)
- **What:** mtga-log-parser now preserves draw results, captures post-match rank, and tracks PlayLand actions; log-ingestion pipeline + ELK dashboard scaffolding added; verified duplicate files removed from the working tree. Test suite: 96 vitest tests, all passing at merge (run by maintainer — they had never been executed).
- **Handling change:** the ELK services (setup, es01, kibana, logstash01) are gated behind the `elk` docker-compose profile (commit bcd492f) so a plain `docker compose up` stays light; opt in with `docker compose --profile elk up`.
- **Why:** richer log parsing feeds the deck/match analysis work; the ELK stack is an opt-in observability tool, not a default boot cost on dev machines.
- **Release state:** dev only (BETA track). Production (stable/importer-fix) untouched.
- **Notes:** `collection.csv` and `backend/arena_helper.db` left the working tree in this merge; both are recoverable from commit 6a494b2 (`git show 6a494b2:<path> > <path>`). Making the new enforce-dev-to-main workflow a required status check on main is a follow-up.
