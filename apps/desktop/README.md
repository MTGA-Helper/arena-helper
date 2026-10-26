# Arena Helper — Desktop (Slices 1–2)

Native desktop shell for Arena Helper: Electron (Windows / macOS / Linux),
a thin client over the live engine API. Slice 1 is the shell, the engine
connection, and auth. Slice 2 adds the collection: stats, the full list
with a list-vs-stats reconciliation line, a name filter, and CSV
upload/refresh. Decks and recommendations deepen in Slices 3–4.

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

## Run

```sh
npm install
npm start
```

Engine base URL defaults to production (`https://arena-helper.onrender.com`);
override with `ARENA_API_BASE` for a local API.

## Verify

```sh
npm run smoke                                   # live engine: health + decks + bad-login + collection reconciliation
ARENA_SMOKE_BASELINE=1 npm run smoke            # + the 12,960-unique-cards production baseline gate
ARENA_API_BASE=http://127.0.0.1:8123 ARENA_SMOKE_AUTH=1 npm run smoke
                                                # auth round-trip — LOCAL api only, never production
ARENA_API_BASE=http://127.0.0.1:8123 ARENA_SMOKE_DECKS=0 ARENA_SMOKE_UPLOAD=1 npm run smoke
                                                # upload round-trip — LOCAL fixture api only (see below)
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
