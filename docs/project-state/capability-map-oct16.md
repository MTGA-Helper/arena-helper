# Arena Helper — Capability Map

**Verified October 16, 2026** against the live system of record: Neon database row counts (post-migration verification), live Render endpoints, and the deployment branch state. Anything not verifiable is marked as roadmap, with its honest stage.

## Naming (decided Oct 16, 2026)

- **Arena Helper** — the MTGA web app + API.
- **Arena Watcher** — the MTGA log-watching agent (local). This is the component outside drafts previously mislabeled "Sentinel."
- **Sentinel** — reserved exclusively for the separate C:\Fire spatial risk-intelligence platform. The name is never used for MTGA components.

## Architecture as it actually stands

- **App:** Arena Helper (web). Deckbuilding UI partial; collection, meta/stats, and overlay UIs are roadmap.
- **API:** Live on Render, deploying from branch `stable/importer-fix`. Routes exist for users, decks, deck analyses, collections, economy, and recommendations. No tournament routes. Match routes exist in concept; match data is effectively empty.
- **Services:** Real but unevenly wired. `next_action_service.py` and deck-analysis logic exist; the synergy engine exists in code. Several services are starved of data (see below).
- **Data:** Neon Postgres 18 (migrated from Render Oct 16, 2026; Render database retained as fallback until it expires Nov 4, 2026). Local Postgres remains the developer system of record.
- **Deployment policy (Billy's, Oct 5):** local-first → separate branch → rebuild → test → tag. The `stable-v1` tag is still pending. A generic main/dev/feature flow is a proposal only, not current practice.

## Live today

| Capability | Evidence |
|---|---|
| Reference card database | 38,906 cards · 118,527 card prints · 38,906 legalities · 13,458 card tags (Neon, verified Oct 16) |
| Deck ingestion & storage | 14 decks · 46 deck cards · 14 deck analyses, served live at /recommendations/decks |
| Deck analysis logic | Service-level, tested (B3 bridge fix verified) |
| Collection ingestion | 12,960 collection rows; end-to-end re-upload verified Oct 6 |
| Authentication | Working end-to-end (4 user accounts) |
| Recommendations endpoint | Live — with one known defect: /recommendations/next-action still serves a hardcoded fallback deck on Render (fix written locally, not yet deployed) |
| Meta card statistics | 45 aggregated rows exist; no tier-list or matchup UI on top of them |
| Hosting split | API on Render + database on Neon, /api/health returning 200 |

## On the roadmap

| Capability | Honest stage |
|---|---|
| Arena Watcher live match pipeline | Code exists; pipeline incomplete — match_histories holds 0 rows |
| Synergy scoring data | Engine exists in code; card_synergies holds 0 rows and the source CSV is empty |
| Economy tracking (gold/gems/wildcards/vault) | Schema exists (wildcard_inventories); 0 rows — no data yet |
| Meta tier lists & matchup tables | Partial aggregation only; no UI |
| Tournaments (creation, pairings, standings, tiebreakers) | Not present — no tables, no routes, no app. Roadmap only |
| In-game overlay (opponent prediction, draw odds, hand/graveyard tracking) | Not present |
| Public deck database UI | Not present (deck data exists; no public library) |
| Draft helper | Not present |
| Player profiles / cloud sync UI | Backend partial; no user-facing system |
| Organizer tools & prize automation | Not present |

## Open items before this map changes

1. Deploy the next-action fix (commit `services/next_action_service.py`, push, redeploy, re-verify) — removes the hardcoded fallback.
2. Tag `stable-v1` once the fix is verified live.
3. Feed the starved pipelines: match log → match_histories; synergy source data → card_synergies.
4. Delete the fallback Render database after a few stable days, before its Nov 4, 2026 expiry.

*Prepared for internal use and the eventual Matt (ELK) handoff — the handoff itself happens only on Billy's word.*
