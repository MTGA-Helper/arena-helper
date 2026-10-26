# Arena Helper — Desktop (Slices 1–6)

Native desktop shell for Arena Helper: Electron (Windows / macOS / Linux),
a thin client over the live engine API. Slice 1 is the shell, the engine
connection, and auth. Slice 2 adds the collection: stats, the full list
with a list-vs-stats reconciliation line, a name filter, and CSV
upload/refresh. Slice 3 adds the Decks view: the engine's ranked deck
list with its completion math checked in the open, and a per-deck
detail — full card list with type lines and subtypes, per-card
owned/missing, and the stored engine analysis shown exactly as
served. Slice 4 adds the Recommendations section (the engine's
next-action answer, with its canned fallback labeled as a
fallback) and deck choosing: every deck's wildcard bill in all
four rarities, priced at each card's cheapest printing with
basics free — the math Matt's Jund Dino hand-check pins at
41 wildcards = 10M / 25R / 5U / 1C.

## Layout

- `main.js` — main process: window + one IPC entry point (`arena:action`).
  The renderer names an action, never a URL. The CSV file picker also
  lives here, so the renderer never touches the filesystem.
- `api.js` — engine API client (main process only). The session token is
  held in memory for the session; nothing is written to disk.
- `preload.js` — context-isolated bridge exposing only `arena.action()`.
- `renderer/` — plain HTML/JS: engine status, sign-in / create-account,
  signed-in home, and the collection view.
- `renderer/collectionLogic.js` — pure list/stats reconciliation + name
  filter, shared by the renderer and the smoke test.
- `renderer/decksLogic.js` — pure deck parity / completion-math /
  detail-summary logic, shared by the renderer and the smoke test.
- `renderer/recommendationsLogic.js` — pure wildcard-bill +
  next-action-view logic (Slice 4), shared the same way.

## Run

```sh
npm install
npm start
```

Engine base URL defaults to production (`https://arena-helper.onrender.com`);
override with `ARENA_API_BASE` for a local API.


## Package (Slice 6)

```sh
npm run dist:mac   # DMG + zip (arm64 on an Apple Silicon build machine)
npm run dist:win   # NSIS installer (cross-built; unsigned)
```

Packaging is electron-builder, configured in `electron-builder.yml`.
Alpha builds are unsigned on purpose — signing / notarization is a
Release-gate item. Artifacts land in `dist/`.

## Verify

```sh
npm run smoke                                   # live engine: health + decks + bad-login + collection reconciliation
ARENA_SMOKE_BASELINE=1 npm run smoke            # + the 12,960-unique-cards production baseline gate
ARENA_API_BASE=http://127.0.0.1:8123 ARENA_SMOKE_AUTH=1 npm run smoke
                                                # auth round-trip — LOCAL api only, never production
ARENA_API_BASE=http://127.0.0.1:8123 ARENA_SMOKE_DECKS=0 ARENA_SMOKE_UPLOAD=1 npm run smoke
                                                # upload round-trip — LOCAL fixture api only (see below)
ARENA_API_BASE=http://127.0.0.1:8123 ARENA_SMOKE_DECKS_FIXTURE=1 npm run smoke
                                                # Slice 3 deck/detail/analysis hand-checks — LOCAL fixture api only (see below)
ARENA_API_BASE=http://127.0.0.1:8123 ARENA_SMOKE_DECKS_FIXTURE=1 ARENA_SMOKE_NEW_DECK=1 npm run smoke
                                                # + the newly-seeded-deck leg, after decks_fixture.py --phase2
ARENA_API_BASE=http://127.0.0.1:8124 ARENA_SMOKE_JUND=1 npm run smoke
                                                # Slice 4 Jund Dino acceptance leg — LOCAL Jund api only (see below)
```

### Local collection fixture (for the upload leg)

The upload endpoint replaces the engine-side collection and its stats
query needs real Postgres (the rarity fix joins card prints), so the
round-trip runs against a scratch local Postgres seeded by
`test/collection_fixture.py`:

```sh
brew install postgresql@16                      # one-time, Mac dev machine
initdb -D /tmp/arena-pg -U arena --auth=trust   # scratch cluster
pg_ctl -D /tmp/arena-pg -o "-p 54329 -k /tmp" -l /tmp/arena-pg.log start
createdb -h /tmp -p 54329 -U arena arena_fixture
export DATABASE_URL="postgresql+asyncpg://arena@127.0.0.1:54329/arena_fixture"
export SYNC_DATABASE_URL="postgresql://arena@127.0.0.1:54329/arena_fixture"
python3 apps/api/init_db.py                     # production table recipe
python3 apps/desktop/test/collection_fixture.py # seed the hand-checkable corpus
PYTHONPATH=. uvicorn apps.api.main:app --port 8123
```

Fixture expectations are printed by the seed script and asserted by the
smoke test (import counts, exact list contents, and stats — including
rares=4 / mythics=2 for a card whose three prints span rare/mythic/rare:
the Phase 0 canonical-print fix, hand-checked end to end).

### Local decks fixture (for the Slice 3 legs)

`test/decks_fixture.py` runs AFTER `test/collection_fixture.py` against
the same scratch database (it reuses that fixture's user) and seeds two
hand-computable decks whose stored analyses are produced by the engine's
own `deck_analysis.analyze_decks`. Its cards carry `type_line` +
`subtypes` exactly as the fixed seed stores them — an older fixture
database needs `apps/api/schema_slice3_subtypes.sql` first (idempotent).

```sh
python3 apps/desktop/test/decks_fixture.py          # Deck A + analysis
# boot the API, run the ARENA_SMOKE_DECKS_FIXTURE=1 smoke above
python3 apps/desktop/test/decks_fixture.py --phase2 # adds Deck B + re-analyzes
# re-run the smoke with ARENA_SMOKE_NEW_DECK=1
```

Fixture expectations are printed by the seed script and asserted by the
smoke test: Deck A completes 71.4% with a 45.25 final analysis score —
the value the engine's own metric definitions produce by hand.

### Local Jund Dino fixture (for the Slice 4 acceptance leg)

`test/jund_fixture.py` seeds a SCRATCH CLONE of the full card corpus
(never the seed database itself) with Matt's "Jund Dino Madness"
Deck Lab submission as an engine deck plus Billy's collection at
the Oct 19, 2026 hand-recorded ownership:

```sh
createdb -h /tmp -p 54329 -U arena arena_slice4 -T arena_seed   # clone the corpus
SYNC_DATABASE_URL=<redacted>
      python3 apps/desktop/test/jund_fixture.py
DATABASE_URL=<redacted> PYTHONPATH=. uvicorn apps.api.main:app --port 8124   # PORT=8124 matters: next-action calls its own port
```

The leg asserts the deck-choosing acceptance numbers end to end
through the app client: 71 required / 30 owned / 42.3% complete,
and a wildcard bill of exactly **41 = 10 mythic / 25 rare /
5 uncommon / 1 common**, with Fabled Passage and Cavern of Souls
priced RARE (their cheapest printings — both have mythic prints),
Seize the Spoils priced COMMON, Bitter Triumph UNCOMMON, and the
three basic lands missing 0.

### Local watcher fixture (for the Slice 5 legs)

`test/watcher_fixture.py` extends the collection fixture (run it
after `test/collection_fixture.py`) with the grpId corpus the watcher
sync resolves against: one print per grpId in `test/fixtures/Player.log`
— a fixture log built from REAL Player.log lines (real decks, real
grpIds, real inventory values) — with grpId 75587 deliberately left
unregistered so the legs can watch an unresolved row land stored-raw:

```sh
SYNC_DATABASE_URL=postgresql://arena@/arena_fixture?host=/tmp&port=54329 \
      python3 apps/desktop/test/watcher_fixture.py
ARENA_API_BASE=http://127.0.0.1:8124 ARENA_SMOKE_DECKS=0 \
  ARENA_SMOKE_AUTH=1 ARENA_SMOKE_UPLOAD=1 ARENA_SMOKE_WATCHER=1 \
      npm run smoke
```

(The fixture api needs `DATABASE_URL`, `SYNC_DATABASE_URL` and
`SECRET_KEY` in its environment — auth reads the sync URL, and the
next-action bridge self-calls on `PORT`.) The legs prove the parse
(real decks + inventory, malformed lines absorbed), the live tail
(append, split line held until its newline, rotation reset), and
the sync round-trip: 2 decks / 32 rows, 31 matched / 1 unmatched,
wildcards moved to the log's 9 rare / 14 mythic. Note the watcher
syncs the deck library + inventory only — the current client never
writes the owned-card collection to the log (verified by a full
scan of two real logs), so the collection stays on the CSV upload.

## Status (Oct 26, 2026 — TURBO surge Day 2, Slice 5)

- Slice 5 verified on the Mac: the Arena Watcher tails Player.log
  and syncs the deck library + wildcard/currency state to the new
  `/watcher` endpoints; grpIds resolve through the seeded
  `CardPrint.arena_id`. Fixture legs (real-log fixtures) all pass,
  the full real 5.5 MB log parses in ~40 ms bounded, Slice 1–4
  regression legs and the live production smoke (incl. the 12,960
  baseline gate) all still pass.
- Not yet verified: the GUI window (no display session over SSH)
  and Windows — the watcher's Windows log path and tail behavior
  are Slice 6 gate items, like the rest of the Windows lane.

## Status (Oct 26, 2026 — TURBO surge Day 2, Slice 4)

- Slice 4 verified on the Mac: the engine's wildcard math now
  prices deficits at each card's cheapest printing and tallies
  all four rarities (basics free), `craft_priority` charges
  copies-to-craft-once (KB gap #12), and the app surfaces the
  next-action recommendation + the deck-choosing bill. Unit
  checks 15/15 (`apps/api/test_slice4_wildcard_math.py`) and the
  Jund acceptance leg passes end to end against a scratch clone
  of the real corpus (41 = 10M/25R/5U/1C exactly). Slice 1–3
  regression legs and the live production smoke (incl. the
  12,960 baseline gate) all still pass.
- Production and the dev service still serve the pre-Slice-4
  bill (rare/mythic keys only, highest-print pricing) until the
  Phase 0 promotion PRs (#22/#23) merge; the app renders both
  shapes correctly (missing buckets read as 0).

## Status (Oct 26, 2026 — TURBO surge Day 2)

- Verified on the Mac: JS syntax; the Electron binary runs (v33.4.11);
  the API client passes its smoke suite against the live engine (health,
  14 decks, bad-login 401, collection list ⇄ stats reconciliation) with
  the production baseline gate green at 12,960 unique cards / 15,296
  total copies; the full auth round-trip and the collection upload
  round-trip pass against a locally booted API on the seeded Postgres
  fixture, including the rarity hand-check.
- Honest limit: production and the dev service still serve the PRE-fix
  rarity counts (rares 25,933 + mythics 7,502 > 15,296 total) — the fix
  is on dev awaiting the Phase 0 promotion PRs (#22/#23, co-captain
  review). The app renders the engine's numbers as they are; against
  the fixed code the same screens show the hand-checked values.
- Not yet verified: the GUI window itself (no display session over SSH) —
  first launch check rides the next Mac pass.
- Windows verification is the next pass: workforce1 and Bills-Flexbook are
  the test targets (Slice 1 gate wants a real Windows + Mac sign-in).
- Environment note: on the Mac, npm's install-scripts gate blocked
  Electron's postinstall download (it fetched a 256 KB stub). Workaround
  used: download the release zip from GitHub directly and unzip it into
  `node_modules/electron/dist`, then write `path.txt`. Standard
  `npm install` should work on an ungated npm.
- Not yet: packaging/installers (Slice 6), token persistence (deliberately
  out of Slice 1). Upload semantics are the endpoint's own: a CSV upload
  replaces the collection (source-of-truth), stated in the UI.
