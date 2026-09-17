# Plan: Hardening & Instrumentation

A set of changes informed by reviewing the parse pipeline end-to-end. The goals are to surface silent failures fast (so MTGA log-format drift can't go undetected for weeks), reduce memory pressure for heavy users, and tighten the seams where existing MTGA quirks already leak through.

Unlike the refactor plans, several of these **do** change behaviour or extend the public API. Each section calls out which.

Suggested order: 1, 2, 5 first — small, independent, instant value. Then 3 and 4, each gated on a short investigation. 6 last, only if a consumer needs it.

---

## 1. Add a `stats` block to `ParseResult` for silent-failure diagnostics

**Scope:** new optional field on the public `ParseResult` interface. Existing consumers ignore it. No internal behaviour change.

**Problem:** `tryParseJSON` swallows errors, the three substring sentinels (`EventSetDeckV2`, `matchGameRoomStateChangedEvent`, `greToClientEvent`) silently miss data if MTGA renames an entry, and "actions with unresolvable grpId are silently dropped" is documented as accepted loss. If WotC renames `EventSetDeckV2` to `EventSetDeckV3`, the parser returns fewer matches with zero signal. The single highest-value change in this plan is making those drops visible.

**Refactor:** Add a counter object threaded through the session and expose it on `ParseResult.stats`. Suggested shape:

```typescript
export interface ParseStats {
  filesScanned: number;
  linesScanned: number;
  candidateLines: { deck: number; matchState: number; gre: number };
  parseErrors:   { deck: number; matchState: number; gre: number };
  matchesStarted: number;
  matchesCompleted: number;
  droppedActions: { unresolvableGrpId: number; orphanTarget: number };
}
```

`tryParseJSON` gains an optional `tag` parameter so callers can bump the right `parseErrors` bucket on failure. The two collectors already have natural drop sites for `droppedActions`.

**Files:** `src/types.ts` (new interface, new field on `ParseResult`), `src/utils.ts` (`tryParseJSON` signature), `src/logParser.ts` (init + thread counters through `ParseSession`), `src/boardStateParser.ts` (increment on action drops), `src/index.ts` (re-export `ParseStats`), tests.

**Why it helps:** The first time MTGA changes a sentinel name, you see `candidateLines.deck = 0` immediately instead of silently missing decks for two weeks. Also useful for users debugging "why doesn't my match X show up?" — non-zero `parseErrors` is a signal.

---

## 2. Stream log files line-by-line instead of `readFile` + `.split('\n')`

**Scope:** no observable behaviour change. Memory profile only.

**Problem:** `readFile(path, 'utf8')` materialises the whole file as a string, then `.split('\n')` allocates a second array of every line. A user with a year of logs may have hundreds of MB per file. Even for typical users, memory bursts during parse are pointless when each line is independent.

**Refactor:** Use Node's built-in `readline` stream interface and feed each line into a smaller `parseLine(line, ps)` helper extracted from `parseLinesAndAddToSession`. The `lines: string[]` field on `ParseSession` goes away.

```typescript
import { createReadStream } from 'fs';
import { createInterface } from 'readline';

async function parseFile(path: string, ps: ParseSession): Promise<void> {
  const rl = createInterface({ input: createReadStream(path, 'utf8') });
  for await (const line of rl) parseLine(line, ps);
}
```

**Files:** `src/logParser.ts` (replace `readFile`/`split` loop, extract `parseLine`), `src/types.ts` (drop `lines` from `ParseSession`).

**Why it helps:** Memory stays flat regardless of total log volume. Also a precondition for #6 — once we're per-file streaming, skipping files by `mtime` is straightforward.

---

## 3. Bound the "trailing GRE messages after MatchCompleted" window

**Scope:** behaviour change. Currently any GRE message arriving after `MatchCompleted` writes into `currentMatchId`'s collectors indefinitely (until the next `MatchPlaying` resets it). This change closes that window after some bound.

**Problem:** The comment in `handleParseMatchStateChange` notes that MTGA "often writes trailing GRE messages for the final turns after the MatchCompleted event" — so `currentMatchId` is intentionally kept set. The trade-off is that *any* later GRE message (a stale flush, an out-of-order log line, a different match that somehow interleaves) gets misattributed silently.

**Investigation first:**
- Grep test fixtures: how many lines after a `MatchCompleted` does the last useful GRE message land? Tens? Hundreds?
- Does any GRE message payload carry its own matchId we could match against? (Probably not — that's why `currentMatchId` exists — but worth confirming.)

**Refactor (if the window is bounded in practice):** track `linesSinceMatchCompleted[matchId]` and stop accepting GRE writes once it exceeds the observed bound + a safety margin. Increment `stats.droppedActions.orphanTarget` (or a new `lateGreMessages` counter) when this fires, so the threshold can be tuned.

**Files:** `src/logParser.ts`, `src/matchHandler.ts`, `src/types.ts` (counter on Session + ParseStats).

**Why it helps:** Closes a silent-corruption class. Whether the bound ends up at "20 lines" or "never fires in practice", the investigation alone is worth it — currently nobody knows.

---

## 4. Verify whether `Targetted` annotations ever land in a later `GameStateMessage` than their `ZoneTransfer`

**Scope:** behaviour change only if findings show it's needed.

**Problem:** Today `pendingActions` is built (Pass 1) and consumed (Pass 2) inside a single `GameStateMessage`. CLAUDE.md is explicit: "Within each `GameStateMessage`". If MTGA ever splits an action's `ZoneTransfer` from its `Targetted` annotation across two messages, the second message's `Targetted` resolves to nothing and the action loses its targets silently.

**Investigation:**
- Grep test fixtures and a real log corpus for `AnnotationType_Targetted`. For each, check whether the same `GameStateMessage` contains a matching `AnnotationType_ZoneTransfer` with the same `sourceId`.
- If you find a counter-example, write a failing test, then refactor.

**Refactor (if needed):** Promote `pendingActions` from a local in `processAnnotations` to a field on `CollectorState`, keyed by `gameKey(matchId, gameNumber)`. Clear entries on turn change (stale targets are worse than dropped ones, but a target arriving one message late should still resolve).

**Files:** `src/boardStateParser.ts`, `src/types.ts` (new field on `CollectorState`).

**Why it helps:** Either confirms the current scope is correct (and the assumption gets verified rather than inherited), or fixes a quiet data-loss bug.

---

## 5. Add Biome as a linter

**Scope:** dev tooling only. No runtime change.

**Problem:** CLAUDE.md notes "There is no linter configured." TypeScript catches type errors, but the codebase indexes heavily into `Record<string, unknown>` — exactly the place where TS *can't* help. Unused imports, dead branches, shadowed locals, accidental `any` via `as` casts all slip through builds today.

**Refactor:** Add `@biomejs/biome` as the only new dev dep — no ESLint plugin dance, single config file. Wire two scripts:

```json
"scripts": {
  "lint":     "biome check src",
  "lint:fix": "biome check --apply src"
}
```

Run once on the current tree and absorb whatever fixes come back in a dedicated commit (separate from any real change) so the diff is reviewable.

**Files:** `package.json` (devDep + 2 scripts), `biome.json` (new), one cleanup commit covering the auto-fixes.

**Why it helps:** A second pair of eyes on every diff at near-zero cost. Catches the kind of mistakes that don't fail builds but rot the codebase over time.

---

## 6. Incremental / cursor-based parsing API

**Scope:** new public function. Existing `parseAllLogs` / `parseAllLogsWithDebug` keep working unchanged.

**Problem:** Every call re-reads every `UTC_Log - *.log` file from disk. For a tool that runs daily, ~95% of the work is re-parsing data that hasn't changed. The per-line scan is cheap; the file I/O isn't free.

**Refactor:** Add `parseLogsSince(config, cursor)` where `cursor` is either:
- a `Date` / epoch number — skip files whose `mtime <= cursor`, or
- a `{ filename, byteOffset }` pair returned from a previous parse — for resume-mid-file precision.

A pragmatic first cut: per-file `mtime` filter, with the result reporting `cursor: number` (the max `mtime` seen). Byte-offset resume can come later if anyone needs it.

This is the largest change in the plan. Worth tackling only if a real consumer needs it. The streaming change in #2 is a precondition (you don't want to re-read whole files just to skip them).

**Files:** `src/logParser.ts`, `src/types.ts` (ParseConfig adds optional `since`, ParseResult adds `cursor`), `src/index.ts` (export the new function).

**Why it helps:** Makes the parser suitable for a daemon, a watch-mode dev tool, or a daily-cron pipeline without paying `O(history)` cost on every run.

---

## What this plan does not address

- **Action drops for opponent hand casts.** Documented but accepted — the grpId resolves once the card hits the stack, so this is rarely a real loss. #1 will at least make the magnitude visible.
- **`opponentColors` requiring a user-provided callback.** This is the right design for a zero-dep library. Keeping it.
- **The substring-prefilter pattern.** It's the right call for log files this verbose. Don't replace it with a streaming JSON parser — the win on irrelevant lines is too big.
