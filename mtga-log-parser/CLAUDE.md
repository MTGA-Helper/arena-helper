# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run build      # compile TypeScript to dist/ (tsc -p tsconfig.build.json)
npm run dev        # watch mode
npm test           # run Vitest test suite (src/__tests__/)
npm run lint       # run Biome linter (check only)
npm run lint:fix   # run Biome linter with auto-fix
npm publish        # runs prepublishOnly (build) then publishes to npm
```

`npm run build` (type-check + emit), `npm test`, and `npm run lint` (Biome) are the three verification steps.

Before publishing, run `rm -rf dist && npm run build` to ensure no stale artifacts from deleted source files end up in the tarball.

## Architecture

The library is a single-pass log parser with no runtime dependencies. All public API is re-exported from `src/index.ts`.

### Data flow

```
UTC_Log - *.log files
        ↓
  parseAllLogsWithDebug  (src/logParser.ts)
        ↓ streams each log file via
  parseFile → parseLine (one call per line)
    ├─ handleParseDeck  (src/deckParser.ts)
    │    └─ → session.deckByEvent / pendingDeckName
    ├─ handleParseMatchStateChange
    │    ├─ handleMatchStart  (src/matchHandler.ts)
    │    └─ handleMatchEnd    (src/matchHandler.ts)
    └─ handleParseGREEventLine
         ├─ tryExtractGameState  (src/matchHandler.ts)
         ├─ gameDataCollector.collect   (src/gameDataParser.ts)
         └─ boardStateCollector.collect (src/boardStateParser.ts)
        ↓
  ParseResult  { matches, gameSnapshots, boardSnapshots, turnDrawRecords, gameActions, stats, deckUsages, … }
```

### Module map

| File | Responsibility |
|---|---|
| `src/logParser.ts` | Entry points (`parseAllLogs`, `parseAllLogsWithDebug`), session wiring; `parseFile` (readline stream) + `parseLine` (sentinel dispatch) |
| `src/types.ts` | Every interface and type alias in the codebase, all exported |
| `src/utils.ts` | Pure utilities: `computeMatchResult`, `parseLogDate`, `tryParseJSON`, `toEntries`, `gameKey` |
| `src/deckParser.ts` | Deck resolution: `extractDeckInfo`, `applyCoursesPayload`, `handleParseDeck` |
| `src/matchHandler.ts` | Match state machine: `handleMatchStart`, `handleMatchEnd`, `tryExtractGameState` |
| `src/gameDataParser.ts` | `createGameDataCollector` — life totals, mulligans, game end reason |
| `src/boardStateParser.ts` | `createBoardStateCollector` — per-phase board snapshots, draw tracking, action tracking |
| `src/rawGameObjects.ts` | GRE JSON → typed struct mapping: `toGameObject`, `mergeGameObject`, `toZone`, `toPlayer`, `toBoardCard` |
| `src/analytics.ts` | `opponentsByPlatform` |

### Key design decisions

**Single-pass, event-driven.** `parseLine` is called per line by `parseFile` (which uses Node `readline` to stream each log file); it scans each line for three sentinel strings (`EventSetDeckV2/CourseDeckSummary`, `matchGameRoomStateChangedEvent`, `greToClientEvent`) and only JSON-parses lines that match. State is accumulated in plain Maps passed by reference.

**Match gating via `matchFilter`.** `handleMatchStart` accepts a `(eventId: string) => boolean` predicate threaded down from `parseAllLogsWithDebug`. The `MatchFilters` export provides presets (`all`, `constructed`, `bo3Constructed`). The default is `MatchFilters.all` — no filtering.

**Deck resolution priority.** Per-event deck lookup (`deckByEvent` map, populated from bulk `Courses` dump at session start or individual `EventSetDeckV2` responses) takes priority over `pendingDeckName` (the last deck seen in the log). This means the correct deck is usually associated even when multiple queues are open.

**`gameEndReason` patching.** In-game `GameStage_GameOver` reasons are unreliable (life deaths can be logged as concedes). `handleMatchEnd` stores raw reasons from `finalMatchResult.resultList` in `gameEndReasonsMap`; these are patched into `GameSnapshot` objects after all files are parsed.

**`opponentColors` resolved in parallel.** After parsing, `resolveColors` is called once per match via `Promise.all`. The callback receives all `grpId`s seen on opponent-owned `GameObjectType_Card` objects.

### All types in `src/types.ts`

Every interface and type alias lives in `src/types.ts` and is exported from there. Source files import what they need from `./types.js`; `src/index.ts` re-exports the public subset. The key output types:

- `Match` — one record per completed match; `game2`/`game3` are `null` for Bo1; includes `opponentPlatform` auto-captured from `reservedPlayers[].platformId`
- `GameSnapshot` — life totals, mulligan counts, turn count, end reason; one per game
- `TurnSnapshot` — full board state snapshot per phase; includes hand, battlefield, graveyard, stack for both players
- `TurnDrawRecord` — grpIds drawn by the local player, one record per turn where a draw occurred
- `GameAction` — one record per spell cast or ability used (both players); includes `type` (`CastSpell`/`ActivateAbility`/`TriggerAbility`), `castByMe`, `sourceGrpId`/`sourceInstanceId`, and `targetGrpIds`/`targetInstanceIds` resolved from game state at cast time
- `ParseStats` — aggregate counters from the parse run: `candidateLines` (sentinel hits per category), `parseErrors` (JSON failures), `droppedActions` (unresolvable grpId or orphan target), plus file/line/match counts
- `DeckList` — `{ main: CardEntry[], sideboard: CardEntry[] }` where each entry is `{ cardId, quantity }`

### Sub-collectors

`createGameDataCollector` and `createBoardStateCollector` are factory functions that return a `collect(raw, matchId, ...)` method and a `snapshots()` method. They process `greToClientEvent / GameStateMessage` payloads independently and are called from `handleParseGREEventLine`.

`boardStateCollector` also exposes `drawRecords()` (returns `TurnDrawRecord[]`), `actionRecords()` (returns `GameAction[]`), and `rawState(matchId, gameNumber)` (returns `RawStateDebug | null` for diagnosing unexpected board snapshots). `rawState` is surfaced on `ParseResult` as `debugBoardState(matchId, gameNumber)`.

**Action tracking uses a two-pass annotation loop.** Within each `GameStateMessage`, Pass 1 scans `AnnotationType_ZoneTransfer` annotations (in `annotations`) with category `CastSpell`, `ActivateAbility`, or `TriggerAbility` and builds stubs in `pendingActionsPerGame` (a collector-scoped Map keyed by `gameKey`). Pass 2 scans `AnnotationType_TargetSpec` annotations in `persistentAnnotations`, reads the top-level `affectorId` field, and attaches target instanceIds/grpIds to the matching pending stub. Stubs are flushed to `actionsByGameKey` on turn-change and in `actionRecords()`. Actions with unresolvable `grpId` (opponent hand cards) are silently dropped and counted in `stats.droppedActions.unresolvableGrpId`.

### ESM-only

`"type": "module"` in `package.json`. Imports within `src/` use `.js` extensions (required for ESM TypeScript). `tsconfig.build.json` emits to `dist/` and excludes test files; `tsconfig.json` is the IDE config.
