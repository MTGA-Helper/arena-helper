# Changelog

All notable changes to `mtga-log-parser` are documented here.

---

## [4.1.0] — 2026-05-16

### Added
- **`ParseStats`** on `ParseResult.stats` — aggregate counters from the parse run: `filesScanned`, `linesScanned`, `candidateLines` (per-sentinel hit counts), `parseErrors` (JSON failure counts per category), `matchesStarted`, `matchesCompleted`, and `droppedActions`. Useful for detecting MTGA log-format drift (e.g. `candidateLines.deck === 0` means the deck sentinel was renamed).
- **Biome linter** — `@biomejs/biome` added as a dev dependency. Two new scripts: `npm run lint` and `npm run lint:fix`.

### Changed
- **Streaming log reads** — `readFile` + `.split('\n')` replaced with Node `readline` / `createReadStream`. Memory footprint is now constant regardless of total log volume.

---

## [4.0.4] — 2026-05-14

### Fixed
- **`isTapped` never clearing** (issue #6) — MTGA does not send `isTapped: false` in delta messages; it signals untap via `AnnotationType_TappedUntappedPermanent`. The annotation loop now processes this annotation to update tap state, so permanents correctly untap at the start of each turn.

---

## [4.0.3] — 2026-05-11

### Fixed
- **Three Pass 2 annotation bugs** (issue #4):
  - Targeting data lives in `persistentAnnotations`, not `annotations`.
  - The annotation type is `AnnotationType_TargetSpec`, not `AnnotationType_Targetted`.
  - The source linkage field is the top-level `affectorId`, not `details[key="sourceId"].valueInt32`.

---

## [4.0.2] — 2026-05-11

### Fixed
- **`targetInstanceIds` always empty** (issue #3) — `pendingActions` was a local Map reset on every `GameStateMessage`. MTGA sometimes writes a `TargetSpec` annotation in a later message than the `ZoneTransfer` that created the action stub. Fixed by promoting `pendingActionsPerGame` to collector scope (keyed by `gameKey`), with explicit flush on turn-change.

---

## [4.0.1] — 2026-05-11

No code changes. Republished with updated README after 4.0.0 was pushed without documentation.

---

## [4.0.0] — 2026-05-11

### Added
- **`GameAction` tracking** — `ParseResult.gameActions: GameAction[]` contains one record per spell cast or ability used in each game. Both players' actions are included where the source `grpId` is resolvable (opponent battlefield is visible; opponent hand is not).
  - Fields: `matchId`, `gameNumber`, `turnNumber`, `type` (`CastSpell` | `ActivateAbility` | `TriggerAbility`), `castByMe`, `sourceGrpId`, `sourceInstanceId`, `targetInstanceIds`, `targetGrpIds`.
  - `targetGrpIds` is resolved from live game state at cast time, so face-down or hidden targets produce an empty array.

---

## [3.0.1] — 2026-05-10

### Fixed
- Mana flood detection producing incorrect results in edge cases.

---

## [3.0.0] — 2026-05-09

### Added
- **`turnDrawRecords: TurnDrawRecord[]`** on `ParseResult` — one record per turn where the local player drew at least one card; contains the `grpId`s of cards drawn in draw order.

### Changed
- **Major module refactor** — source split into dedicated files: `deckParser.ts`, `matchHandler.ts`, `rawGameObjects.ts`. Improves maintainability and isolates responsibilities.
- **`boardStateCollector` removed from `ParseResult`** — replaced with `debugBoardState(matchId, gameNumber)`, a function that returns `RawStateDebug | null`. Consumers that were calling `result.boardStateCollector.snapshots()` should use `result.boardSnapshots` instead (already filtered to completed matches). See migration guide in README.

### Fixed
- Match results assigned from the wrong game entry when a player timed out before all games completed.

---

## [2.3.6] — 2026-05-03

### Added
- `oppHandCount: number` on `TurnSnapshot` — opponent's hand size at the time of the snapshot.

---

## [2.3.5] — 2026-05-02

### Fixed
- Turn grouping: immediate board-state emission and combat continuity tracking so phases within the same turn are correctly grouped rather than split across turn boundaries.

---

## [2.3.4] — 2026-05-02

### Fixed
- Turn number mis-stamping in deferred board-state emit — snapshots were being attributed to the wrong turn when MTGA advanced the turn counter before all phase events were logged.

---

## [2.3.2] — 2026-05-01

### Fixed
- `RawZone` was reading `ownerId` instead of `ownerSeatId`, causing zone-to-player attribution to fail.

---

## [2.3.1] — 2026-04-30

### Fixed
- `currentMatchId` was cleared immediately on `MatchCompleted`, dropping trailing GRE messages that MTGA writes for the final turns after the match-end event. `currentMatchId` is now retained until the next `MatchPlaying` event.

---

## [2.3.0] — 2026-04-30

### Added
- `match.opponentPlatform: string` — opponent's client platform auto-detected from `reservedPlayers[].platformId` (e.g. `"Mac"`, `"Windows"`, `"iOS"`, `"Android"`).
- `opponentsByPlatform(matches)` analytics helper — returns a count of matches per platform.

---

## [2.2.3] — 2026-04-30

### Fixed
- Life-total fallback: `GameStage_GameOver` sometimes omits life totals on life-total deaths. The parser now uses the last life totals seen in any preceding message as a fallback.
- `gameResults` array was indexed incorrectly, causing game 2/3 results to be misattributed.
- `gameNumber` assertion was not bounds-checked, causing a crash on malformed log entries.

---

## [2.2.0] — 2026-04-28

### Added
- `GameSnapshot.openingHandGrpIds?: number[]` — the `grpId`s of the initial 7-card hand before any mulligan decision.

---

## [2.0.0] — 2026-04-26

### Changed
- **Breaking: format-agnostic by default.** The parser now returns all match formats instead of only Bo3. Add `matchFilter: MatchFilters.bo3Constructed` to your config to restore the previous behavior.
- **`MatchFilters` export** — `MatchFilters.all`, `MatchFilters.constructed`, `MatchFilters.bo3Constructed` presets; or pass a custom `(eventId: string) => boolean` predicate.

---

## [1.0.0] — 2026-04-26

Initial release. Parses MTGA `UTC_Log - *.log` files and returns:
- `Match[]` — completed matches with result, play/draw, deck name, opponent platform, and opponent colors.
- `GameSnapshot[]` — per-game life totals, mulligan counts, turn count, and end reason.
- `TurnSnapshot[]` — per-phase board state for every turn (hand, battlefield, graveyard, exile, stack for both players).
- `DeckList` maps and deck usage history.
- Async `resolveColors` callback for opponent color detection via the MTGA card database.
