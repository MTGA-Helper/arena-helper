import { readdir, stat } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import { join } from 'node:path';
import type { Match, GameSnapshot, TurnSnapshot, TurnDrawRecord, GameAction, ParseConfig, ParseResult, DeckList, Session, ParseSession, ParseStats } from './types.js';
import { isGameStateMessage, parseLogDate, tryParseJSON } from './utils.js';
import { createGameDataCollector } from './gameDataParser.js';
import { createBoardStateCollector } from './boardStateParser.js';
import { handleParseDeck } from './deckParser.js';
import { handleMatchStart, handleMatchEnd, tryExtractGameState } from './matchHandler.js';

export const MatchFilters = {
  /** Traditional_ prefix (ranked + seasonal events) and Constructed_BestOf3 only */
  bo3Constructed: (eventId: string): boolean =>
    eventId.startsWith('Traditional_') || eventId === 'Constructed_BestOf3',

  /** All constructed formats — excludes draft, sealed, and jump-in */
  constructed: (eventId: string): boolean =>
    Boolean(eventId) && !/(Draft|Sealed|Jump_?In)/i.test(eventId),

  /** All matches — the default when matchFilter is omitted */
  all: (): boolean => true,
} as const;

function handleParseMatchStateChange(line: string, session: Session, ps: ParseSession) {
  const obj = tryParseJSON(line, () => { ps.stats.parseErrors.matchState++; });
  if (obj && typeof obj === 'object') {
    const raw = obj as Record<string, unknown>;
    const event = raw.matchGameRoomStateChangedEvent as Record<string, unknown> | undefined;
    if (event) {
      const gameRoomInfo = event.gameRoomInfo as Record<string, unknown> | undefined;
      const stateType = (event.stateType ?? gameRoomInfo?.stateType) as string | undefined;

      if (stateType === 'MatchGameRoomStateType_Playing' && gameRoomInfo) {
        ps.stats.matchesStarted++;
        handleMatchStart(raw, gameRoomInfo, session.matchMap, session.localTeamIdMap, session.pendingDeckName, session.myDeckListMap, session.pendingDeckList, session.deckByEvent, ps.matchFilter, session.localPlayerId);
        // Track current match for GRE message association
        const config = gameRoomInfo.gameRoomConfig as Record<string, unknown> | undefined;
        const matchId = config?.matchId as string | undefined;
        if (matchId) {
          session.currentMatchId = matchId;
          // Build seatId→teamId map so GRE systemSeatIds can correct the localTeamId
          // (platformId === 'Mac' fails when both players are on Mac)
          const reservedPlayers = config?.reservedPlayers as Array<Record<string, unknown>> | undefined;
          if (reservedPlayers) {
            const seatTeam = new Map<number, number>();
            for (const p of reservedPlayers) {
              const s = p.systemSeatId, t = p.teamId;
              if (typeof s === 'number' && typeof t === 'number') seatTeam.set(s, t);
            }
            session.seatToTeamByMatch.set(matchId, seatTeam);
          }
        }

        const players = config?.reservedPlayers as Array<Record<string, unknown>> | undefined;
        const rawEventId = (players?.[0]?.eventId as string) ?? '';
        const ts = typeof raw.timestamp === 'string' ? parseInt(raw.timestamp, 10) : 0;
        const eventDeck = session.deckByEvent.get(rawEventId);
        const name = eventDeck?.name ?? session.pendingDeckName;
        const deck = eventDeck?.deck ?? session.pendingDeckList;
        if (name && !name.startsWith('?=?')) {
          const existing = session.deckUsages.get(name);
          if (!existing || ts > existing.timestamp) {
            session.deckUsages.set(name, { deck, timestamp: ts });
          }
        }
      } else if (stateType === 'MatchGameRoomStateType_MatchCompleted' && gameRoomInfo) {
        ps.stats.matchesCompleted++;
        handleMatchEnd(gameRoomInfo, session.matchMap, session.localTeamIdMap, session.gameEndReasonsMap);
        // Do NOT null currentMatchId here — MTGA often writes trailing GRE messages for
        // the final turns after the MatchCompleted event. Keeping currentMatchId set lets
        // the board state and game data collectors capture those. The next MatchPlaying
        // event naturally replaces it when the next match begins.
      }
    }
  }
}

function handleParseGREEventLine(line: string, session: Session, ps: ParseSession) {
  const obj = tryParseJSON(line, () => { ps.stats.parseErrors.gre++; });
  if (obj && typeof obj === 'object') {
    const raw = obj as Record<string, unknown>;

    // Correct localTeamId using GRE systemSeatIds — more reliable than the platformId
    // heuristic, which fails when both players are on Mac. Use the first GRE message
    // seen for each match (subsequent messages are the same seat so no need to repeat).
    if (session.currentMatchId && !session.localTeamIdGREConfirmed.has(session.currentMatchId)) {
      const gteEvent = raw.greToClientEvent as Record<string, unknown> | undefined;
      const msgs = gteEvent?.greToClientMessages as Array<Record<string, unknown>> | undefined;
      if (msgs) {
        for (const msg of msgs) {
          if (!isGameStateMessage(msg)) continue;
          const seatIds = msg.systemSeatIds as number[] | undefined;
          const localSeatId = seatIds?.[0];
          if (typeof localSeatId !== 'number') continue;
          const teamId = session.seatToTeamByMatch.get(session.currentMatchId)?.get(localSeatId);
          if (typeof teamId === 'number') {
            session.localTeamIdMap.set(session.currentMatchId, teamId);
            session.localTeamIdGREConfirmed.add(session.currentMatchId);
          }
          break;
        }
      }
    }

    tryExtractGameState(raw, session.matchMap, session.currentMatchId, session.opponentGrpIds);
    ps.gameDataCollector.collect(raw, session.currentMatchId, session.localTeamIdMap);
    ps.boardStateCollector.collect(raw, session.currentMatchId, ps.stats);
  }
}

function parseEntry(entry: string, ps: ParseSession): void {
  const session = ps.session;

  const parsed = tryParseJSON(entry);
  if (parsed && typeof parsed === 'object') {
    const raw = parsed as Record<string, unknown>;
    const auth = raw.authenticateResponse as Record<string, unknown> | undefined;
    if (typeof auth?.clientId === 'string') session.localPlayerId = auth.clientId;
  }

  // Deck name + card list detection: EventSetDeckV2 response or CourseDeckSummary
  if (entry.includes('EventSetDeckV2') || entry.includes('CourseDeckSummary')) {
    ps.stats.candidateLines.deck++;
    handleParseDeck(entry, session, () => { ps.stats.parseErrors.deck++; });
  }

  // Match state changes
  if (entry.includes('matchGameRoomStateChangedEvent')) {
    ps.stats.candidateLines.matchState++;
    handleParseMatchStateChange(entry, session, ps);
  }

  // Play/draw + opponent card detection + game snapshot data from GRE state messages
  if (entry.includes('greToClientEvent') && entry.includes('GameStateMessage')) {
    ps.stats.candidateLines.gre++;
    handleParseGREEventLine(entry, session, ps);
  }
}

async function parseFile(path: string, ps: ParseSession): Promise<void> {
  const rl = createInterface({ input: createReadStream(path, 'utf8'), crlfDelay: Infinity });
  let entry: string[] = [];

  const flush = () => {
    if (entry.length > 0) parseEntry(entry.join('\n'), ps);
    entry = [];
  };

  for await (const line of rl) {
    ps.stats.linesScanned++;
    const trimmed = line.trimStart();
    const startsEntry = line.startsWith('[UnityCrossThreadLogger]') || trimmed.startsWith('<==');
    if (startsEntry) flush();

    // Ignore boot diagnostics before the first structured entry, but allow
    // standalone JSON records for compatibility with older exported fixtures.
    if (startsEntry || entry.length > 0 || trimmed.startsWith('{')) entry.push(line);
  }
  flush();
}

export async function parseAllLogs(config: ParseConfig): Promise<Match[]> {
  return (await parseAllLogsWithDebug(config)).matches;
}

function buildNewSession(matchFilter: (eventId: string) => boolean): ParseSession {
  const emptyDeck: DeckList = { main: [], sideboard: [] };
  const stats: ParseStats = {
    filesScanned: 0,
    linesScanned: 0,
    candidateLines: { deck: 0, matchState: 0, gre: 0 },
    parseErrors:   { deck: 0, matchState: 0, gre: 0 },
    matchesStarted: 0,
    matchesCompleted: 0,
    droppedActions: { unresolvableGrpId: 0, orphanTarget: 0 },
  };
  return {
    matchFilter,
    stats,
    session: {
      localPlayerId: null,
      matchMap: new Map(),
      localTeamIdMap: new Map(),
      opponentGrpIds: new Map(),
      myDeckListMap: new Map(),
      pendingDeckName: '',
      pendingDeckList: emptyDeck,
      currentMatchId: null,
      deckByEvent: new Map(),
      gameEndReasonsMap: new Map(),
      deckUsages: new Map(),
      seatToTeamByMatch: new Map(),
      localTeamIdGREConfirmed: new Set(),
    },
    gameDataCollector: createGameDataCollector(),
    boardStateCollector: createBoardStateCollector(),
  };
}

export async function parseAllLogsWithDebug(config: ParseConfig): Promise<ParseResult> {
  const input = await stat(config.logDir);
  const logFiles = input.isFile()
    ? [config.logDir]
    : (await readdir(config.logDir))
      .filter((f) => (f.startsWith('UTC_Log') && f.endsWith('.log')) || /^Player(?:-prev)?\.log$/.test(f))
      .sort((a, b) => parseLogDate(a) - parseLogDate(b));

  const effectiveFilter = config.matchFilter ?? MatchFilters.all;
  const ps = buildNewSession(effectiveFilter);

  for (const filename of logFiles) {
    ps.stats.filesScanned++;
    await parseFile(input.isFile() ? filename : join(config.logDir, filename), ps);
  }

  const { matchMap, opponentGrpIds, myDeckListMap, gameEndReasonsMap, deckUsages } = ps.session;
  const { gameDataCollector, boardStateCollector } = ps;

  // Derive opponent colors from collected grpIds via optional callback — resolved in parallel
  await Promise.all(
    Array.from(opponentGrpIds.entries()).map(async ([matchId, grpSet]) => {
      const existing = matchMap.get(matchId);
      if (!existing) return;
      const colors = (await config.resolveColors?.(Array.from(grpSet))) ?? '';
      if (colors) matchMap.set(matchId, { ...existing, opponentColors: colors });
    }),
  );

  const matches = Array.from(matchMap.values()).filter((m) => m.matchResult !== null);

  // Filter snapshots to only completed matches
  const matchIds = new Set(matches.map((m) => m.id));

  // Patch game end reasons from finalMatchResult — more reliable than in-game GameStage_GameOver
  // reasons which can mislabel life-total deaths as concedes.
  const rawGameSnapshots = gameDataCollector.snapshots().filter((s) => matchIds.has(s.matchId));
  const gameSnapshots: GameSnapshot[] = rawGameSnapshots.map((s) => {
    const rawReason = gameEndReasonsMap.get(s.matchId)?.[s.gameNumber - 1];
    if (!rawReason) return s;
    const gameEndReason: GameSnapshot['gameEndReason'] =
      rawReason === 'ResultReason_Life' ? 'life' :
      rawReason === 'ResultReason_Concede' ? 'concede' :
      rawReason === 'ResultReason_Timeout' ? 'timeout' :
      rawReason === 'ResultReason_Draw' ? 'draw' : 'unknown';
    return { ...s, gameEndReason };
  });

  const boardSnapshots: TurnSnapshot[] = boardStateCollector.snapshots().filter((s) => matchIds.has(s.matchId));
  const turnDrawRecords: TurnDrawRecord[] = boardStateCollector.drawRecords().filter((r) => matchIds.has(r.matchId));
  const gameActions: GameAction[] = boardStateCollector.actionRecords().filter((a) => matchIds.has(a.matchId));

  return {
    matches,
    opponentGrpIds,
    gameSnapshots,
    boardSnapshots,
    turnDrawRecords,
    gameActions,
    myDeckListMap,
    deckUsages,
    debugBoardState: (matchId, gameNumber) => boardStateCollector.rawState(matchId, gameNumber),
    stats: ps.stats,
  };
}
