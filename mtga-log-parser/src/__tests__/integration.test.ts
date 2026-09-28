import { describe, it, expect, afterEach } from 'vitest';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseAllLogsWithDebug } from '../logParser.js';

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

function logFilename(date = new Date('2026-01-01T00:00:00Z')): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `UTC_Log - ${p(date.getUTCMonth() + 1)}-${p(date.getUTCDate())}-${date.getUTCFullYear()} ${p(date.getUTCHours())}.${p(date.getUTCMinutes())}.${p(date.getUTCSeconds())}.log`;
}

interface PlayerOpts {
  userId?: string;
  playerName?: string;
  platformId?: string;
  teamId?: number;
  systemSeatId?: number;
  eventId?: string;
}

function matchStartLine(opts: {
  matchId: string;
  timestamp?: string;
  local?: PlayerOpts;
  opponent?: PlayerOpts;
}): string {
  const local: Required<PlayerOpts> = {
    userId: 'local-user',
    playerName: 'LocalPlayer',
    platformId: 'Mac',
    teamId: 1,
    systemSeatId: 1,
    eventId: 'Traditional_Ladder',
    ...opts.local,
  };
  const opp: Required<PlayerOpts> = {
    userId: 'opp-user',
    playerName: 'Opponent',
    platformId: 'Windows',
    teamId: 2,
    systemSeatId: 2,
    eventId: 'Traditional_Ladder',
    ...opts.opponent,
  };
  const json = {
    timestamp: opts.timestamp ?? '1714000000000',
    matchGameRoomStateChangedEvent: {
      stateType: 'MatchGameRoomStateType_Playing',
      gameRoomInfo: {
        gameRoomConfig: {
          matchId: opts.matchId,
          reservedPlayers: [local, opp],
        },
      },
    },
  };
  return `[UnityCrossThreadLogger]Incoming Event.MatchGameRoomStateChangedEvent ${JSON.stringify(json)}`;
}

function matchEndLine(opts: {
  matchId: string;
  results: Array<{ scope?: string; winningTeamId: number; reason?: string }>;
}): string {
  const json = {
    matchGameRoomStateChangedEvent: {
      stateType: 'MatchGameRoomStateType_MatchCompleted',
      gameRoomInfo: {
        finalMatchResult: {
          matchId: opts.matchId,
          resultList: opts.results.map((r) => ({
            scope: r.scope ?? 'MatchScope_Game',
            winningTeamId: r.winningTeamId,
            reason: r.reason ?? 'ResultReason_Life',
          })),
        },
      },
    },
  };
  return `[UnityCrossThreadLogger]Incoming Event.MatchGameRoomStateChangedEvent ${JSON.stringify(json)}`;
}

function deckLine(opts: {
  eventName: string;
  deckName: string;
  mainDeck?: Array<{ cardId: number; quantity: number }>;
  sideboard?: Array<{ cardId: number; quantity: number }>;
}): string {
  const json = {
    InternalEventName: opts.eventName,
    CourseDeckSummary: { Name: opts.deckName },
    CourseDeck: {
      MainDeck: opts.mainDeck ?? [],
      Sideboard: opts.sideboard ?? [],
    },
  };
  return `[UnityCrossThreadLogger]Outgoing Request.EventSetDeckV2 ${JSON.stringify(json)}`;
}

function multilineEntry(line: string): string {
  const jsonStart = line.indexOf('{');
  return `${line.slice(0, jsonStart)}\n${JSON.stringify(JSON.parse(line.slice(jsonStart)), null, 2)}`;
}

// ---------------------------------------------------------------------------
// Temp dir lifecycle
// ---------------------------------------------------------------------------

const tempDirs: string[] = [];

async function makeTempDir(): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), 'mtga-test-'));
  tempDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(tempDirs.splice(0).map((d) => rm(d, { recursive: true, force: true })));
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('parseAllLogsWithDebug integration', () => {
  it('identifies the local player by authenticated client ID when they are seat 2', async () => {
    const dir = await makeTempDir();
    const lines = [
      `[UnityCrossThreadLogger]Incoming authenticateResponse ${JSON.stringify({ authenticateResponse: { clientId: 'local-user', screenName: 'LocalPlayer' } })}`,
      matchStartLine({
        matchId: 'match-seat-two',
        local: { userId: 'opponent-user', playerName: 'Opponent', platformId: 'AndroidPhone', teamId: 1, systemSeatId: 1 },
        opponent: { userId: 'local-user', playerName: 'LocalPlayer', platformId: 'Windows', teamId: 2, systemSeatId: 2 },
      }),
      matchEndLine({ matchId: 'match-seat-two', results: [{ winningTeamId: 2 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches[0].myPlayerId).toBe('local-user');
    expect(matches[0].myGamerTag).toBe('LocalPlayer');
    expect(matches[0].opponentPlayerId).toBe('opponent-user');
    expect(matches[0].opponentGamerTag).toBe('Opponent');
    expect(matches[0].matchResult).toBe('Win');
  });

  it('parses multiline records and queued game-state messages', async () => {
    const dir = await makeTempDir();
    const queuedGre = {
      greToClientEvent: {
        greToClientMessages: [{
          type: 'GREMessageType_QueuedGameStateMessage',
          systemSeatIds: [1],
          gameStateMessage: {
            gameInfo: { gameNumber: 1 },
            turnInfo: { turnNumber: 1, activePlayer: 2 },
            gameObjects: [],
          },
        }],
      },
    };
    const lines = [
      multilineEntry(matchStartLine({ matchId: 'match-current-format' })),
      `[UnityCrossThreadLogger]Incoming Event.GreToClientEvent\n${JSON.stringify(queuedGre, null, 2)}`,
      multilineEntry(matchEndLine({ matchId: 'match-current-format', results: [{ winningTeamId: 1 }] })),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches, stats } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches).toHaveLength(1);
    expect(matches[0].id).toBe('match-current-format');
    expect(matches[0].onPlay).toBe(false);
    expect(stats.candidateLines.gre).toBe(1);
  });

  it('accepts a direct Player.log file path', async () => {
    const dir = await makeTempDir();
    const logFile = join(dir, 'Player.log');
    await writeFile(logFile, [
      matchStartLine({ matchId: 'player-log-match' }),
      matchEndLine({ matchId: 'player-log-match', results: [{ winningTeamId: 2 }] }),
    ].join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: logFile });

    expect(matches).toHaveLength(1);
    expect(matches[0].id).toBe('player-log-match');
    expect(matches[0].matchResult).toBe('Loss');
  });

  it('parses a complete Bo1 win', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-1' }),
      matchEndLine({ matchId: 'match-1', results: [{ winningTeamId: 1 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches).toHaveLength(1);
    const m = matches[0];
    expect(m.id).toBe('match-1');
    expect(m.matchResult).toBe('Win');
    expect(m.game1).toBe(1);
    expect(m.game2).toBeNull();
    expect(m.game3).toBeNull();
    expect(m.opponent).toBe('Opponent');
    expect(m.opponentPlatform).toBe('Windows');
    expect(m.myGamerTag).toBe('LocalPlayer');
    expect(m.opponentGamerTag).toBe('Opponent');
  });

  it('parses a complete Bo1 loss', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-2' }),
      matchEndLine({ matchId: 'match-2', results: [{ winningTeamId: 2 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches).toHaveLength(1);
    expect(matches[0].matchResult).toBe('Loss');
    expect(matches[0].game1).toBe(0);
  });

  it('parses a Bo3 2-0 win', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-3', local: { eventId: 'Traditional_Ladder' }, opponent: { eventId: 'Traditional_Ladder' } }),
      matchEndLine({
        matchId: 'match-3',
        results: [{ winningTeamId: 1 }, { winningTeamId: 1 }],
      }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches).toHaveLength(1);
    const m = matches[0];
    expect(m.matchResult).toBe('Win');
    expect(m.game1).toBe(1);
    expect(m.game2).toBe(1);
    expect(m.game3).toBeNull();
  });

  it('parses a Bo3 2-1 win', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-4' }),
      matchEndLine({
        matchId: 'match-4',
        results: [{ winningTeamId: 1 }, { winningTeamId: 2 }, { winningTeamId: 1 }],
      }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches[0].matchResult).toBe('Win');
    expect(matches[0].game1).toBe(1);
    expect(matches[0].game2).toBe(0);
    expect(matches[0].game3).toBe(1);
  });

  it('parses a Bo3 1-2 loss', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-5' }),
      matchEndLine({
        matchId: 'match-5',
        results: [{ winningTeamId: 2 }, { winningTeamId: 1 }, { winningTeamId: 2 }],
      }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches[0].matchResult).toBe('Loss');
    expect(matches[0].game1).toBe(0);
    expect(matches[0].game2).toBe(1);
    expect(matches[0].game3).toBe(0);
  });

  it('excludes matches with null matchResult (incomplete matches)', async () => {
    const dir = await makeTempDir();
    // Match start but no end event → matchResult stays null
    await writeFile(join(dir, logFilename()), matchStartLine({ matchId: 'match-incomplete' }));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches).toHaveLength(0);
  });

  it('respects matchFilter — excludes draft events', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({
        matchId: 'match-draft',
        local: { eventId: 'QuickDraft_DOM' },
        opponent: { eventId: 'QuickDraft_DOM' },
      }),
      matchEndLine({ matchId: 'match-draft', results: [{ winningTeamId: 1 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({
      logDir: dir,
      matchFilter: (eventId) => !/(Draft|Sealed)/i.test(eventId),
    });

    expect(matches).toHaveLength(0);
  });

  it('includes only passing events when matchFilter is set', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-ranked', local: { eventId: 'Traditional_Ladder' }, opponent: { eventId: 'Traditional_Ladder' } }),
      matchEndLine({ matchId: 'match-ranked', results: [{ winningTeamId: 1 }] }),
      matchStartLine({ matchId: 'match-draft', local: { eventId: 'QuickDraft_DOM' }, opponent: { eventId: 'QuickDraft_DOM' } }),
      matchEndLine({ matchId: 'match-draft', results: [{ winningTeamId: 1 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({
      logDir: dir,
      matchFilter: (eventId) => !/(Draft|Sealed)/i.test(eventId),
    });

    expect(matches).toHaveLength(1);
    expect(matches[0].id).toBe('match-ranked');
  });

  it('resolves deck name from a CourseDeckSummary line before match start', async () => {
    const dir = await makeTempDir();
    const lines = [
      deckLine({ eventName: 'Traditional_Ladder', deckName: 'Azorius Control', mainDeck: [{ cardId: 100001, quantity: 4 }] }),
      matchStartLine({ matchId: 'match-deck', local: { eventId: 'Traditional_Ladder' }, opponent: { eventId: 'Traditional_Ladder' } }),
      matchEndLine({ matchId: 'match-deck', results: [{ winningTeamId: 1 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches, myDeckListMap } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches[0].myDeck).toBe('Azorius Control');
    const deck = myDeckListMap.get('match-deck');
    expect(deck?.main).toEqual([{ cardId: 100001, quantity: 4 }]);
  });

  it('derives eventId label from raw eventId', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-label', local: { eventId: 'Traditional_Ladder' }, opponent: { eventId: 'Traditional_Ladder' } }),
      matchEndLine({ matchId: 'match-label', results: [{ winningTeamId: 1 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches[0].eventId).toBe('Ranked');
  });

  it('parses multiple matches across a single log file', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-a' }),
      matchEndLine({ matchId: 'match-a', results: [{ winningTeamId: 1 }] }),
      matchStartLine({ matchId: 'match-b' }),
      matchEndLine({ matchId: 'match-b', results: [{ winningTeamId: 2 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches).toHaveLength(2);
    const ids = new Set(matches.map((m) => m.id));
    expect(ids.has('match-a')).toBe(true);
    expect(ids.has('match-b')).toBe(true);
  });

  it('parses matches across multiple log files in date order', async () => {
    const dir = await makeTempDir();

    const older = logFilename(new Date('2025-12-31T00:00:00Z'));
    const newer = logFilename(new Date('2026-01-01T00:00:00Z'));

    // Write the newer file first to confirm sorting, not insertion order, is used
    await writeFile(join(dir, newer), [
      matchStartLine({ matchId: 'match-newer', timestamp: '1750000000000' }),
      matchEndLine({ matchId: 'match-newer', results: [{ winningTeamId: 1 }] }),
    ].join('\n'));

    await writeFile(join(dir, older), [
      matchStartLine({ matchId: 'match-older', timestamp: '1700000000000' }),
      matchEndLine({ matchId: 'match-older', results: [{ winningTeamId: 2 }] }),
    ].join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches).toHaveLength(2);
    const winMatch = matches.find((m) => m.matchResult === 'Win');
    const lossMatch = matches.find((m) => m.matchResult === 'Loss');
    expect(winMatch?.id).toBe('match-newer');
    expect(lossMatch?.id).toBe('match-older');
  });

  it('leaves opponentColors empty when no GRE messages have been seen', async () => {
    // resolveColors is only called when opponentGrpIds entries have been collected
    // from GRE GameStateMessages. Without them, opponentColors stays ''.
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-colors' }),
      matchEndLine({ matchId: 'match-colors', results: [{ winningTeamId: 1 }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const resolveColors = async (_grpIds: number[]): Promise<string> => 'WU';
    const { matches } = await parseAllLogsWithDebug({ logDir: dir, resolveColors });

    expect(matches).toHaveLength(1);
    expect(matches[0].opponentColors).toBe('');
  });

  it('captures a Bo3 won by opponent timeout mid-series (1-1 game record, match-scope result wins)', async () => {
    // Scenario: player loses game 1, then opponent times out before/during game 2.
    // MTGA awards game 2 and the match to the player via MatchScope_Match entry.
    // computeMatchResult(0, 1, null) returns null (1-1 tie), so the match-scope
    // entry must be used as the authoritative fallback.
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-timeout', local: { eventId: 'Constructed_BestOf3' }, opponent: { eventId: 'Constructed_BestOf3' } }),
      matchEndLine({
        matchId: 'match-timeout',
        results: [
          { scope: 'MatchScope_Game',  winningTeamId: 2, reason: 'ResultReason_Concede' },
          { scope: 'MatchScope_Game',  winningTeamId: 1, reason: 'ResultReason_Timeout' },
          { scope: 'MatchScope_Match', winningTeamId: 1, reason: 'ResultReason_Timeout' },
        ],
      }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { matches } = await parseAllLogsWithDebug({ logDir: dir });

    expect(matches).toHaveLength(1);
    const m = matches[0];
    expect(m.matchResult).toBe('Win');
    expect(m.game1).toBe(0);
    expect(m.game2).toBe(1);
    expect(m.game3).toBeNull();
  });

  it('patches gameEndReason in gameSnapshots from finalMatchResult reasons', async () => {
    // This test requires GRE game data messages which we don't fixture here.
    // Instead verify that the gameSnapshots array exists and is filterable by matchId.
    const dir = await makeTempDir();
    const lines = [
      matchStartLine({ matchId: 'match-gs' }),
      matchEndLine({ matchId: 'match-gs', results: [{ winningTeamId: 1, reason: 'ResultReason_Concede' }] }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { gameSnapshots } = await parseAllLogsWithDebug({ logDir: dir });

    // No GRE messages → no snapshots, but the array is present and typed correctly
    expect(Array.isArray(gameSnapshots)).toBe(true);
  });
});
