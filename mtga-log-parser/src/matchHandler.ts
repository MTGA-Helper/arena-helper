import type { Match, GameResult, DeckList, RawGameResult} from './types.js';
import { computeMatchResult, isGameStateMessage} from './utils.js';

export function handleMatchStart(
  obj: Record<string, unknown>,
  gameRoomInfo: Record<string, unknown>,
  matchMap: Map<string, Match>,
  localTeamIdMap: Map<string, number>,
  pendingDeckName: string,
  myDeckListMap: Map<string, DeckList>,
  pendingDeckList: DeckList,
  deckByEvent: Map<string, { name: string; deck: DeckList }>,
  matchFilter: (eventId: string) => boolean,
  localPlayerId: string | null,
): void {
  const config = gameRoomInfo.gameRoomConfig as Record<string, unknown> | undefined;
  if (!config) return;

  const matchId = config.matchId as string | undefined;
  if (!matchId) return;

  const players = config.reservedPlayers as Array<Record<string, unknown>> | undefined;
  if (!players || players.length < 2) return;

  const allPass = players.every((p) => {
    const eventId = p.eventId;
    return typeof eventId === 'string' && matchFilter(eventId);
  });
  if (!allPass) return;

  // Prefer the authenticated account ID. Seat and platform are not stable:
  // the local player can be seat 2 or use Windows/iOS/Android.
  let localPlayer = localPlayerId
    ? players.find((p) => p.userId === localPlayerId)
    : undefined;
  // Fallback for logs without authenticateResponse identity data.
  if (!localPlayer) localPlayer = players.find((p) => p.platformId === 'Mac');
  if (!localPlayer) localPlayer = players.find((p) => p.systemSeatId === 1);
  if (!localPlayer) localPlayer = players[0];

  const opponent = players.find((p) => p.userId !== localPlayer?.userId);
  if (!opponent) return;

  const localTeamId = localPlayer.teamId;
  if (typeof localTeamId !== 'number') return;
  localTeamIdMap.set(matchId, localTeamId);

  const timestamp =
    typeof obj.timestamp === 'string' ? parseInt(obj.timestamp, 10) : Date.now();

  // Derive a friendly event label from the first player's eventId
  const rawEventId = players[0]?.eventId as string | undefined ?? '';
  const eventLabel = rawEventId === 'Traditional_Ladder' ? 'Ranked'
    : rawEventId.startsWith('Traditional_') ? rawEventId.replace(/^Traditional_/, '').replace(/_/g, ' ')
    : rawEventId === 'Constructed_BestOf3' ? 'Bo3 Play'
    : rawEventId === 'Play' ? 'Bo1 Play'
    : rawEventId === 'PlayRanked' ? 'Bo1 Ranked'
    : rawEventId === 'AIBotMatch' ? 'Bot Match'
    : rawEventId;

  // Prefer per-event deck lookup (from Courses dump or individual EventSetDeckV2).
  // Fall back to pendingDeckName (last-seen deck) only if no event-specific entry exists.
  const eventDeck = deckByEvent.get(rawEventId);
  const resolvedDeckName = eventDeck?.name ?? pendingDeckName;
  const resolvedDeckList = eventDeck?.deck ?? pendingDeckList;

  myDeckListMap.set(matchId, resolvedDeckList);

  matchMap.set(matchId, {
    id: matchId,
    timestamp,
    myPlayerId: (localPlayer.userId as string) ?? '',
    opponentPlayerId: (opponent.userId as string) ?? '',
    myGamerTag: (localPlayer.playerName as string) ?? '',
    opponentGamerTag: (opponent.playerName as string) ?? '',
    opponent: (opponent.playerName as string) ?? 'Unknown',
    opponentPlatform: (opponent.platformId as string) ?? '',
    opponentDeck: '',
    opponentColors: '',
    myDeck: resolvedDeckName,
    onPlay: null,
    game1: null,
    game2: null,
    game3: null,
    matchResult: null,
    eventId: eventLabel,
    importedAt: Date.now(),
    notes: '',
  });
}

export function handleMatchEnd(
  gameRoomInfo: Record<string, unknown>,
  matchMap: Map<string, Match>,
  localTeamIdMap: Map<string, number>,
  gameEndReasonsMap: Map<string, string[]>,
): void {
  const finalResult = gameRoomInfo.finalMatchResult as Record<string, unknown> | undefined;
  if (!finalResult) return;

  const matchId = finalResult.matchId as string | undefined;
  if (!matchId) return;

  const existing = matchMap.get(matchId);
  if (!existing) return;
  if (existing.game1 !== null) return; // already processed

  const localTeamId = localTeamIdMap.get(matchId);
  if (localTeamId === undefined) return;

  const resultList = finalResult.resultList as Array<Record<string, unknown>> | undefined;
  if (!resultList) return;

  const gameResults: RawGameResult[] = resultList
    .filter((r) => r.scope === 'MatchScope_Game')
    .flatMap((r) => {
      const winningTeamId = r.winningTeamId;
      const reason = r.reason;
      if (typeof winningTeamId !== 'number' || typeof reason !== 'string') return [];
      return [{ winningTeamId, reason }];
    });

  // Store the raw per-game reasons so the caller can patch GameSnapshot.gameEndReason.
  // The in-game GameStage_GameOver reasons are unreliable (e.g. life deaths sometimes log
  // as ResultReason_Concede); finalMatchResult.resultList is the authoritative source.
  gameEndReasonsMap.set(matchId, gameResults.map((r) => r.reason));

  const games: GameResult[] = gameResults.map((r) => {
    if (r.reason === 'ResultReason_Draw') return 'Draw';
    return r.winningTeamId === localTeamId ? 1 : 0;
  });

  const g1: GameResult = games[0] ?? null;
  const g2: GameResult = games[1] ?? null;
  const g3: GameResult = games[2] ?? null;

  // Primary: derive result from game scores. Fallback: use the match-scope entry in
  // resultList for cases where game scores are tied (e.g. 1-1 when the opponent times
  // out or forfeits mid-series — MTGA awards the match without playing a decisive game).
  let matchResult = computeMatchResult(g1, g2, g3);
  if (matchResult === null) {
    const matchScopeEntry = resultList.find((r) => r.scope === 'MatchScope_Match');
    const matchWinningTeamId = matchScopeEntry?.winningTeamId;
    if (typeof matchWinningTeamId === 'number') {
      matchResult = matchWinningTeamId === localTeamId ? 'Win' : 'Loss';
    }
  }

  matchMap.set(matchId, {
    ...existing,
    game1: g1,
    game2: g2,
    game3: g3,
    matchResult,
  });
}

// Try to extract onPlay and opponent grpIds from GRE GameStateMessages
// currentMatchId is tracked by the caller from match start/end events
export function tryExtractGameState(
  obj: Record<string, unknown>,
  matchMap: Map<string, Match>,
  currentMatchId: string | null,
  opponentGrpIds: Map<string, Set<number>>,
): void {
  if (!currentMatchId) return;
  const existing = matchMap.get(currentMatchId);
  if (!existing) return;

  const gteEvent = obj.greToClientEvent as Record<string, unknown> | undefined;
  if (!gteEvent) return;

  const messages = gteEvent.greToClientMessages as Array<Record<string, unknown>> | undefined;
  if (!messages) return;

  for (const msg of messages) {
    if (!isGameStateMessage(msg)) continue;

    const seatIds = msg.systemSeatIds as number[] | undefined;
    const localSeatId = seatIds?.[0];
    if (typeof localSeatId !== 'number') continue;

    const gsm = msg.gameStateMessage as Record<string, unknown> | undefined;
    if (!gsm) continue;

    // Collect opponent grpIds from game objects (battlefield, graveyard = visible)
    const gameObjects = gsm.gameObjects as Array<Record<string, unknown>> | undefined;
    if (gameObjects) {
      if (!opponentGrpIds.has(currentMatchId)) opponentGrpIds.set(currentMatchId, new Set());
      const grpSet = opponentGrpIds.get(currentMatchId)!;
      for (const go of gameObjects) {
        const owner = go.ownerSeatId;
        const grp = go.grpId;
        // Only opponent-owned, real card grpIds (> 100 to skip special token IDs)
        if (typeof owner === 'number' && owner !== localSeatId && typeof grp === 'number' && grp > 100 && go.type === 'GameObjectType_Card') {
          grpSet.add(grp);
        }
      }
    }

    // Play/draw detection: game 1, turn 1 only
    const gameInfo = gsm.gameInfo as Record<string, unknown> | undefined;
    if (gameInfo?.gameNumber !== 1) continue;

    const turnInfo = gsm.turnInfo as Record<string, unknown> | undefined;
    if (!turnInfo) continue;

    const turnNumber = turnInfo.turnNumber;
    const activePlayer = turnInfo.activePlayer;
    if (typeof turnNumber !== 'number' || turnNumber !== 1) continue;
    if (typeof activePlayer !== 'number') continue;

    if (existing.onPlay === null) {
      matchMap.set(currentMatchId, { ...existing, onPlay: activePlayer === localSeatId });
    }
  }
}
