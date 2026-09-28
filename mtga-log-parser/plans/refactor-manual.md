# Plan: Manual Learning Refactors

Two small structural refactors to do by hand. Neither changes behaviour. The goal is to read and understand the code you're touching rather than letting a tool do it.

---

## ~~1. Move `gameKey` from `rawGameObjects.ts` to `utils.ts`~~ (Done)

**What:** `gameKey(matchId, gameNumber)` is a one-line pure function that produces a string key. It lives in `src/rawGameObjects.ts` but has nothing to do with raw JSON mapping — it belongs in `src/utils.ts` alongside the other stateless utilities.

**Files to touch:**
- `src/rawGameObjects.ts` — delete the `gameKey` function
- `src/utils.ts` — add it here (no imports needed, it takes two primitives)
- `src/boardStateParser.ts` — update the import line (currently imports `gameKey` from `./rawGameObjects.js`, move it to `./utils.js`)
- `src/logParser.ts` — check if it imports `gameKey`; update if so

**How to verify:** `npm run build` — the compiler will catch any missed import updates.

**What you'll learn:** How the ESM import graph is wired, how `rawGameObjects.ts` and `boardStateParser.ts` relate, where the "pure utilities" boundary sits.

---

## ~~2. Extract `processAnnotations` from `boardStateParser.collect()`~~ (Done)

**What:** The `collect()` function in `src/boardStateParser.ts` is the largest function in the codebase. Inside it, the annotation-processing block (~200 lines) handles draw tracking (Pass 1 for draws) and action tracking (Pass 1 for ZoneTransfer, Pass 2 for TargetSpec). Extract this block into a standalone helper function `processAnnotations(...)`.

**The signature you need to work out:**

```typescript
function processAnnotations(
  gsm: Record<string, unknown>,
  state: LiveGameState,
  currentMatchId: string,
  gameNumber: number,
  drawsByTurnKey: Map<string, TurnDrawRecord>,
  pendingActionsPerGame: Map<string, { actions: Map<number, GameAction>; turn: number }>,
  actionsByGameKey: Map<string, GameAction[]>,
): void
```

The function reads from `gsm['annotations']` and `gsm['persistentAnnotations']`, looks up objects via `state.gameObjects` and `state.localSeatId`, and writes into `drawsByTurnKey`, `pendingActionsPerGame`, and `actionsByGameKey`.

**Where to put it:** Define `processAnnotations` just above `createBoardStateCollector` (alongside `buildSnapshot` and `createCollectorState`). Then replace the annotation block inside `collect()` with a single call:

```typescript
processAnnotations(gsm, state, currentMatchId, gameNumber, drawsByTurnKey, pendingActionsPerGame, actionsByGameKey);
```

**Files to touch:**
- `src/boardStateParser.ts` only

**How to verify:** `npm run build && npm test` — all 80 tests should still pass with no changes to logic.

**What you'll learn:** The annotation system from the inside — exactly what state the draw and action loops read and write, how `pendingActionsPerGame` is threaded through, and how Pass 1 (ZoneTransfer) and Pass 2 (TargetSpec) interact. This is the densest part of the codebase and the best place to build a mental model of how the v4 action tracking actually works.
