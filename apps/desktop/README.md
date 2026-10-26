# Arena Helper — Desktop (Slice 1 scaffold)

Native desktop shell for Arena Helper: Electron (Windows / macOS / Linux),
a thin client over the live engine API. Slice 1 scope is the shell, the
engine connection, and auth — collection, decks, and recommendations land
in Slices 2–4.

## Layout

- `main.js` — main process: window + one IPC entry point (`arena:action`).
  The renderer names an action, never a URL.
- `api.js` — engine API client (main process only). The session token is
  held in memory for the session; nothing is written to disk.
- `preload.js` — context-isolated bridge exposing only `arena.action()`.
- `renderer/` — plain HTML/JS: engine status, sign-in / create-account,
  signed-in home showing the live recommended-deck count.

## Run

```sh
npm install
npm start
```

Engine base URL defaults to production (`https://arena-helper.onrender.com`);
override with `ARENA_API_BASE` for a local API.

## Verify

```sh
npm run smoke                                   # live engine: health + decks + bad-login rejection
ARENA_API_BASE=http://127.0.0.1:8123 ARENA_SMOKE_AUTH=1 npm run smoke
                                                # auth round-trip — LOCAL api only, never production
```

## Status (Oct 26, 2026 — TURBO surge Day 1)

- Verified on the Mac: JS syntax; the Electron binary runs (v33.4.11);
  the API client passes its smoke suite against the live engine (health,
  14 decks, bad-login 401) and the full auth round-trip (register → login
  → token held → logout) against a locally booted API instance.
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
  out of Slice 1), any collection data (Slice 2).
