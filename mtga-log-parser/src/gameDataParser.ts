import type { GameSnapshot, GameDataCollector, SnapshotBuilder } from './types.js';
import { gameKey, isGameStateMessage } from './utils.js';

function parseEndReason(reason: string): GameSnapshot['gameEndReason'] {
  if (reason === 'ResultReason_Concede') return 'concede';
  if (reason === 'ResultReason_Life') return 'life';
  if (reason === 'ResultReason_Timeout') return 'timeout';
  if (reason === 'ResultReason_Draw') return 'draw';
  return 'unknown';
}

export function createGameDataCollector(): GameDataCollector {
  const builders = new Map<string, SnapshotBuilder>();
  const completed: GameSnapshot[] = [];
  // Track current game number: updated whenever we see gameInfo.gameNumber
  // Keyed by matchId so games from different matches don't bleed into each other
  const currentGameNumbers = new Map<string, number>();
  // Persist local seat ID across messages — GameStage_GameOver may not carry systemSeatIds
  const localSeatIds = new Map<string, number>();

  function getBuilder(matchId: string, gameNumber: number): SnapshotBuilder {
    const key = gameKey(matchId, gameNumber);
    if (!builders.has(key)) builders.set(key, { myMulligan: 0, oppMulligan: 0, lastMyLife: null, lastOppLife: null, openingHandCaptured: false, openingHandGrpIds: [] });
    return builders.get(key)!;
  }

  function collect(
    obj: Record<string, unknown>,
    currentMatchId: string | null,
    localTeamIdMap: Map<string, number>,
  ): void {
    if (!currentMatchId) return;

    const gteEvent = obj.greToClientEvent as Record<string, unknown> | undefined;
    if (!gteEvent) return;
    const messages = gteEvent.greToClientMessages as Array<Record<string, unknown>> | undefined;
    if (!messages) return;

    for (const msg of messages) {
      if (!isGameStateMessage(msg)) continue;

      // Persist local seat ID — GameStage_GameOver messages may omit systemSeatIds
      const seatIds = msg.systemSeatIds as number[] | undefined;
      const msgSeatId = typeof seatIds?.[0] === 'number' ? seatIds[0] : undefined;
      if (msgSeatId !== undefined) localSeatIds.set(currentMatchId, msgSeatId);
      const localSeatId = localSeatIds.get(currentMatchId);
      if (localSeatId === undefined) continue;

      const gsm = msg.gameStateMessage as Record<string, unknown> | undefined;
      if (!gsm) continue;

      const gameInfo = gsm.gameInfo as Record<string, unknown> | undefined;

      // Arena emits a second GameStage_GameOver message for the match-level
      // result after the game-level result. Only the game-level message creates
      // a snapshot; otherwise each game is recorded twice.
      if (gameInfo?.matchState === 'MatchState_MatchComplete') continue;

      // Update tracked game number whenever we see it in a message
      const gameNumberRaw = gameInfo?.gameNumber;
      if (typeof gameNumberRaw === 'number') {
        currentGameNumbers.set(currentMatchId, gameNumberRaw);
      }

      const currentGameNumber = currentGameNumbers.get(currentMatchId);
      if (typeof currentGameNumber !== 'number') continue;

      const players = gsm.players as Array<Record<string, unknown>> | undefined;

      // Mulligan tracking + life total tracking. Life totals here serve as fallback for
      // the GameStage_GameOver handler, which sometimes omits lifeTotal on death events.
      const builder = getBuilder(currentMatchId, currentGameNumber);
      if (players) {
        for (const p of players) {
          const seat = p.systemSeatNumber;
          const mc = p.mulliganCount;
          if (typeof mc === 'number') {
            if (seat === localSeatId) builder.myMulligan = Math.max(builder.myMulligan, mc);
            else builder.oppMulligan = Math.max(builder.oppMulligan, mc);
          }
          const life = p.lifeTotal;
          if (typeof life === 'number') {
            if (seat === localSeatId) builder.lastMyLife = life;
            else builder.lastOppLife = life;
          }
        }
      }

      // Capture opening hand grpIds from the first message where the local player's hand
      // zone has cards. The initial deal arrives as a GameStateType_Diff (the preceding Full
      // message establishes empty hand zones). Zones use ownerSeatId, not ownerId.
      if (!builder.openingHandCaptured) {
        const zones = gsm.zones as Array<Record<string, unknown>> | undefined;
        const gameObjects = gsm.gameObjects as Array<Record<string, unknown>> | undefined;
        if (zones && gameObjects) {
          const handZone = zones.find(
            (z) => z.type === 'ZoneType_Hand' && z.ownerSeatId === localSeatId,
          );
          if (handZone) {
            const instanceIds = Array.isArray(handZone.objectInstanceIds)
              ? (handZone.objectInstanceIds as unknown[]).filter((x): x is number => typeof x === 'number')
              : [];
            const instanceIdSet = new Set(instanceIds);
            const grpIds = gameObjects
              .filter(
                (o) =>
                  typeof o.instanceId === 'number' &&
                  instanceIdSet.has(o.instanceId as number) &&
                  typeof o.grpId === 'number',
              )
              .map((o) => o.grpId as number);
            // Only capture when we have a full 7-card opening hand. MTGA always deals the
            // initial hand as a single Diff message, so < 7 means a partial batch and we
            // should wait for the rest rather than locking openingHandCaptured prematurely.
            if (grpIds.length >= 7) {
              builder.openingHandGrpIds = grpIds;
              builder.openingHandCaptured = true;
            }
          }
        }
      }

      // Game end: capture final life, turn count, and end reason
      if (gameInfo?.stage !== 'GameStage_GameOver') continue;
      if (!players || players.length === 0) continue;

      if (currentGameNumber < 1 || currentGameNumber > 3) continue;
      const gameNumber = currentGameNumber as 1 | 2 | 3;

      // results[] is cumulative across all games; the last entry is the current game's result.
      const results = gameInfo.results as Array<Record<string, unknown>> | undefined;
      const gameResults = results?.filter((r) => r.scope === 'MatchScope_Game') ?? [];
      const thisGameResult = gameResults[gameResults.length - 1];
      const endReason = thisGameResult
        ? parseEndReason(thisGameResult.reason as string)
        : 'unknown';

      const myPlayer = players.find((p) => p.systemSeatNumber === localSeatId);
      const oppPlayer = players.find((p) => p.systemSeatNumber !== localSeatId);

      const myFinalLife = typeof myPlayer?.lifeTotal === 'number'
        ? (myPlayer.lifeTotal as number)
        : (builder.lastMyLife ?? 20);
      const oppFinalLife = typeof oppPlayer?.lifeTotal === 'number'
        ? (oppPlayer.lifeTotal as number)
        : (builder.lastOppLife ?? 20);

      const myTurns = typeof myPlayer?.turnNumber === 'number' ? (myPlayer.turnNumber as number) : 0;
      const oppTurns = typeof oppPlayer?.turnNumber === 'number' ? (oppPlayer.turnNumber as number) : 0;
      const turnCount = Math.max(myTurns, oppTurns);

      completed.push({
        matchId: currentMatchId,
        gameNumber,
        myMulliganCount: builder.myMulligan,
        opponentMulliganCount: builder.oppMulligan,
        myFinalLife,
        opponentFinalLife: oppFinalLife,
        turnCount,
        gameEndReason: endReason,
        openingHandGrpIds: builder.openingHandGrpIds.length > 0 ? builder.openingHandGrpIds : undefined,
      });

      // Suppress unused parameter warning — localTeamIdMap is accepted for API compatibility
      // but game data parsing uses localSeatId (from systemSeatIds) rather than teamId.
      void localTeamIdMap;
    }
  }

  return { collect, snapshots: () => completed };
}
