# Plan: Module Extraction Refactors

Structural refactors to redistribute existing code into cohesive homes. None of these change behaviour.

---

## Completed

**Interfaces → `src/types.ts`**
All interfaces and type aliases from every file consolidated into a single `src/types.ts`. The `src/types/` directory (4 separate files) was deleted. Every type is exported from `types.ts`; all source files import from `./types.js`. `src/index.ts` re-exports public API types from a single `export type { ... } from './types.js'` block.

**`src/utils.ts` — pure utility functions**
`computeMatchResult`, `parseLogDate`, `tryParseJSON`, and `toEntries` extracted from `logParser.ts` into `src/utils.ts`, all exported. Duplicate definitions removed from `logParser.ts`. Tests updated to import `computeMatchResult` and `parseLogDate` from `../utils.js`.

---

## ~~1. Extract `src/deckParser.ts` — deck resolution subsystem~~ (Done)

**Problem:** `applyCoursesPayload`, `extractDeckInfo`, and `handleParseDeck` form a self-contained subsystem — all three exist solely to populate `session.deckByEvent` and `session.pendingDeckName`. `extractDeckInfo` is exported for tests, which looks out of place in the same file as `parseAllLogs`.

**Refactor:** Create `src/deckParser.ts` and move `applyCoursesPayload`, `extractDeckInfo`, and `handleParseDeck` there. `CardEntry`, `DeckList`, and `toEntries` are already in their proper homes (`types.ts` and `utils.ts` respectively) — no type movement needed.

```
src/deckParser.ts
  function applyCoursesPayload(courses, deckByEvent): void
  export function extractDeckInfo(obj): { name, deck } | null
  export function handleParseDeck(line, session): void
```

`handleParseDeck` imports `tryParseJSON` from `./utils.js`, `extractDeckInfo` from within the same file, and `Session` from `./types.js`. `logParser.ts` imports `extractDeckInfo` and `handleParseDeck` from `./deckParser.js`. Update tests to import `extractDeckInfo` from `../deckParser.js`.

**Files:** `src/deckParser.ts` (new), `src/logParser.ts`, `src/__tests__/unit.test.ts`

**Why it helps:** "Where does deck name resolution live?" has a one-word answer. `logParser.ts` stops owning functions that are unrelated to the parsing loop.

---

## ~~2. Extract `src/matchHandler.ts` — match start/end handlers~~ (Done)

**Problem:** `handleMatchStart`, `handleMatchEnd`, and `tryExtractGameState` are ~200 lines of match state machine logic embedded in `logParser.ts`. They're called from only two places (`handleParseMatchStateChange` and `handleParseGREEventLine`) but their implementations are buried far from those call sites.

**Refactor:** Create `src/matchHandler.ts` and move all three functions there. They take only typed parameters (Maps, raw objects) — no closure state — so this is a straight move. `RawGameResult` is already in `types.ts`.

```
src/matchHandler.ts
  export function handleMatchStart(...)
  export function handleMatchEnd(...)
  export function tryExtractGameState(...)
```

Dependencies: imports `computeMatchResult` from `./utils.js`; imports `Match`, `GameResult`, `DeckList`, `RawGameResult` from `./types.js`. `logParser.ts` imports all three from `./matchHandler.js`.

**Files:** `src/matchHandler.ts` (new), `src/logParser.ts`

**Why it helps:** `logParser.ts` becomes a composition file — it wires up sub-handlers rather than implementing them. After this task `logParser.ts` drops to ~250 lines covering only session setup and the line-routing loop.

---

## ~~3. Extract `src/rawGameObjects.ts` — JSON-to-struct mapping functions~~ (Done)

**Problem:** `boardStateParser.ts` opens with five mapping functions (`toGameObject`, `mergeGameObject`, `toZone`, `toPlayer`, `toBoardCard`) before getting to any snapshot or collector logic. These are mechanical raw-JSON-to-typed-struct transforms that share no logic with the snapshot builder or the event-routing code.

**Refactor:** Create `src/rawGameObjects.ts` and move the five functions there. All interfaces they reference (`RawGameObject`, `RawZone`, `RawPlayer`, `LiveGameState`, `BoardCard`) are already in `types.ts`.

```
src/rawGameObjects.ts
  export function toGameObject(raw): RawGameObject | null
  export function mergeGameObject(existing, raw, parsed): RawGameObject
  export function toZone(raw): RawZone | null
  export function toPlayer(raw): RawPlayer
  export function toBoardCard(obj): BoardCard
```

`boardStateParser.ts` imports the five functions from `./rawGameObjects.js`.

**Files:** `src/rawGameObjects.ts` (new), `src/boardStateParser.ts`

**Why it helps:** `boardStateParser.ts` opens with `buildSnapshot` and `createBoardStateCollector` rather than 80 lines of JSON mapping. The mapping code is independently findable.

---

## After all tasks: expected file sizes

| File | Now | After |
|---|---|---|
| `src/logParser.ts` | 484 lines | ~250 lines |
| `src/boardStateParser.ts` | 559 lines | ~480 lines |
| `src/gameDataParser.ts` | 169 lines | no change |
| `src/utils.ts` | 47 lines | no change |
| `src/types.ts` | 259 lines | no change |
| `src/deckParser.ts` | — | ~80 lines |
| `src/matchHandler.ts` | — | ~210 lines |
| `src/rawGameObjects.ts` | — | ~80 lines |
