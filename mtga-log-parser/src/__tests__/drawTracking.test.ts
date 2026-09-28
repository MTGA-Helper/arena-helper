import { describe, it, expect, afterEach } from 'vitest';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseAllLogsWithDebug } from '../logParser.js';
import { createBoardStateCollector } from '../boardStateParser.js';

// ---------------------------------------------------------------------------
// Fixture helpers (shared with integration.test.ts pattern)
// ---------------------------------------------------------------------------

function logFilename(date = new Date('2026-01-01T00:00:00Z')): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `UTC_Log - ${p(date.getUTCMonth() + 1)}-${p(date.getUTCDate())}-${date.getUTCFullYear()} ${p(date.getUTCHours())}.${p(date.getUTCMinutes())}.${p(date.getUTCSeconds())}.log`;
}

function matchStartLine(matchId: string): string {
  const json = {
    timestamp: '1714000000000',
    matchGameRoomStateChangedEvent: {
      stateType: 'MatchGameRoomStateType_Playing',
      gameRoomInfo: {
        gameRoomConfig: {
          matchId,
          reservedPlayers: [
            { userId: 'local', playerName: 'Local', platformId: 'Mac', teamId: 1, systemSeatId: 1, eventId: 'Traditional_Ladder' },
            { userId: 'opp',   playerName: 'Opp',   platformId: 'Windows', teamId: 2, systemSeatId: 2, eventId: 'Traditional_Ladder' },
          ],
        },
      },
    },
  };
  return `[UnityCrossThreadLogger]Incoming Event.MatchGameRoomStateChangedEvent ${JSON.stringify(json)}`;
}

function matchEndLine(matchId: string, winningTeamId = 1): string {
  const json = {
    matchGameRoomStateChangedEvent: {
      stateType: 'MatchGameRoomStateType_MatchCompleted',
      gameRoomInfo: {
        finalMatchResult: {
          matchId,
          resultList: [{ scope: 'MatchScope_Game', winningTeamId, reason: 'ResultReason_Life' }],
        },
      },
    },
  };
  return `[UnityCrossThreadLogger]Incoming Event.MatchGameRoomStateChangedEvent ${JSON.stringify(json)}`;
}

/**
 * Build a GRE GameStateMessage line that includes:
 * - the given game objects (with grpId visible — as they would be for the local player's hand)
 * - ZoneTransfer/Draw annotations referencing the given instanceIds
 * - turnInfo with the given turnNumber and activePlayer
 */
function greDrawLine(opts: {
  matchId: string;
  gameNumber: number;
  turnNumber: number;
  localSeatId: number;
  activePlayer?: number;
  /** Cards drawn this message: each card is added to gameObjects AND referenced by a Draw annotation. */
  draws: Array<{ instanceId: number; grpId: number; ownerSeatId: number }>;
  gameStateType?: string;
}): string {
  const { gameNumber, turnNumber, localSeatId, draws, gameStateType = 'GameStateType_Diff' } = opts;
  const activePlayer = opts.activePlayer ?? localSeatId;

  const gameObjects = draws.map((d) => ({
    instanceId: d.instanceId,
    grpId: d.grpId,
    ownerSeatId: d.ownerSeatId,
    controllerSeatId: d.ownerSeatId,
    type: 'GameObjectType_Card',
    zoneId: 10, // hand zone
  }));

  const annotations = draws.map((d, i) => ({
    id: 1000 + i,
    type: 'AnnotationType_ZoneTransfer',
    details: [{ key: 'category', valueString: ['Draw'] }],
    affectedIds: [d.instanceId],
  }));

  const json = {
    greToClientEvent: {
      greToClientMessages: [
        {
          type: 'GREMessageType_GameStateMessage',
          systemSeatIds: [localSeatId],
          gameStateMessage: {
            type: gameStateType,
            gameInfo: { gameNumber },
            turnInfo: { turnNumber, activePlayer },
            gameObjects,
            annotations,
          },
        },
      ],
    },
  };
  return `[UnityCrossThreadLogger]Incoming Event.GreToClientEvent ${JSON.stringify(json)}`;
}

// ---------------------------------------------------------------------------
// Temp dir lifecycle
// ---------------------------------------------------------------------------

const tempDirs: string[] = [];

async function makeTempDir(): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), 'mtga-draw-test-'));
  tempDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(tempDirs.splice(0).map((d) => rm(d, { recursive: true, force: true })));
});

// ---------------------------------------------------------------------------
// Unit tests for createBoardStateCollector draw tracking
// ---------------------------------------------------------------------------

describe('createBoardStateCollector draw tracking', () => {
  it('records a single draw on turn 1', () => {
    const collector = createBoardStateCollector();

    const msg = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 1, activePlayer: 1 },
              gameObjects: [
                { instanceId: 101, grpId: 5001, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 10 },
              ],
              annotations: [
                { id: 1, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [101] },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-1');

    const records = collector.drawRecords();
    expect(records).toHaveLength(1);
    expect(records[0]).toMatchObject({
      matchId: 'match-1',
      gameNumber: 1,
      turnNumber: 1,
      drawnGrpIds: [5001],
    });
  });

  it('records multiple draws on the same turn in order', () => {
    const collector = createBoardStateCollector();

    const msg = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 3, activePlayer: 1 },
              gameObjects: [
                { instanceId: 201, grpId: 6001, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card' },
                { instanceId: 202, grpId: 6002, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card' },
              ],
              annotations: [
                { id: 1, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [201] },
                { id: 2, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [202] },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-2');

    const records = collector.drawRecords();
    expect(records).toHaveLength(1);
    expect(records[0].drawnGrpIds).toEqual([6001, 6002]);
  });

  it('accumulates draws across multiple messages on the same turn', () => {
    const collector = createBoardStateCollector();

    const makeMsg = (instanceId: number, grpId: number, turnNumber = 2) => ({
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber, activePlayer: 1 },
              gameObjects: [
                { instanceId, grpId, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card' },
              ],
              annotations: [
                { id: instanceId, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [instanceId] },
              ],
            },
          },
        ],
      },
    });

    collector.collect(makeMsg(301, 7001) as Record<string, unknown>, 'match-3');
    collector.collect(makeMsg(302, 7002) as Record<string, unknown>, 'match-3');

    const records = collector.drawRecords();
    expect(records).toHaveLength(1);
    expect(records[0].drawnGrpIds).toEqual([7001, 7002]);
    expect(records[0].turnNumber).toBe(2);
  });

  it('creates separate records for different turns', () => {
    const collector = createBoardStateCollector();

    const makeMsg = (instanceId: number, grpId: number, turnNumber: number) => ({
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber, activePlayer: 1 },
              gameObjects: [
                { instanceId, grpId, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card' },
              ],
              annotations: [
                { id: instanceId, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [instanceId] },
              ],
            },
          },
        ],
      },
    });

    collector.collect(makeMsg(401, 8001, 1) as Record<string, unknown>, 'match-4');
    collector.collect(makeMsg(402, 8002, 3) as Record<string, unknown>, 'match-4');

    const records = collector.drawRecords();
    expect(records).toHaveLength(2);

    const turn1 = records.find((r) => r.turnNumber === 1);
    const turn3 = records.find((r) => r.turnNumber === 3);
    expect(turn1?.drawnGrpIds).toEqual([8001]);
    expect(turn3?.drawnGrpIds).toEqual([8002]);
  });

  it('ignores draws for the opponent (unresolvable grpId or different ownerSeatId)', () => {
    const collector = createBoardStateCollector();

    // Opponent's card: ownerSeatId=2, but local seat is 1.
    // grpId is absent for face-down opponent hand cards — simulating that below.
    const msg = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 2, activePlayer: 2 },
              // Opponent's card: ownerSeatId=2. No grpId (hand is hidden).
              gameObjects: [
                { instanceId: 501, ownerSeatId: 2, controllerSeatId: 2, type: 'GameObjectType_Card' },
              ],
              annotations: [
                { id: 1, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [501] },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-5');

    expect(collector.drawRecords()).toHaveLength(0);
  });

  it('excludes turn-0 draws (opening hand / mulligan iterations)', () => {
    // Turn 0 is the opening hand deal. When a player mulligans, MTGA sends multiple
    // Full messages at turnNumber=0, each with Draw annotations. These must NOT produce
    // TurnDrawRecord entries because opening hands are tracked separately via
    // openingHandGrpIds on GameSnapshot.
    const collector = createBoardStateCollector();

    const makeTurn0Msg = (instanceId: number, grpId: number) => ({
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Full',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 0, activePlayer: 1 },
              gameObjects: [
                { instanceId, grpId, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 10 },
              ],
              annotations: [
                { id: instanceId, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [instanceId] },
              ],
            },
          },
        ],
      },
    });

    // Simulate two mulligan iterations at turn 0
    collector.collect(makeTurn0Msg(101, 5001) as Record<string, unknown>, 'match-mulligan');
    collector.collect(makeTurn0Msg(102, 5002) as Record<string, unknown>, 'match-mulligan');
    collector.collect(makeTurn0Msg(103, 5003) as Record<string, unknown>, 'match-mulligan');
    collector.collect(makeTurn0Msg(104, 5004) as Record<string, unknown>, 'match-mulligan');
    collector.collect(makeTurn0Msg(105, 5005) as Record<string, unknown>, 'match-mulligan');

    // No TurnDrawRecord entries should exist for turn 0
    expect(collector.drawRecords()).toHaveLength(0);
  });

  it('ignores annotations that are not ZoneTransfer/Draw category', () => {
    const collector = createBoardStateCollector();

    const msg = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 1, activePlayer: 1 },
              gameObjects: [
                { instanceId: 601, grpId: 9001, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card' },
              ],
              annotations: [
                // Wrong type
                { id: 1, type: 'AnnotationType_ResolutionComplete', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [601] },
                // Right type, wrong category
                { id: 2, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['CastSpell'] }], affectedIds: [601] },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-6');

    expect(collector.drawRecords()).toHaveLength(0);
  });

  it('ignores draws for unknown instanceIds (not in gameObjects map)', () => {
    const collector = createBoardStateCollector();

    const msg = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 1, activePlayer: 1 },
              // No gameObjects — instanceId 701 is not in the map
              gameObjects: [],
              annotations: [
                { id: 1, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [701] },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-7');

    expect(collector.drawRecords()).toHaveLength(0);
  });

  it('creates separate records for different games', () => {
    const collector = createBoardStateCollector();

    const makeMsg = (instanceId: number, grpId: number, gameNumber: number) => ({
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber },
              turnInfo: { turnNumber: 1, activePlayer: 1 },
              gameObjects: [
                { instanceId, grpId, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card' },
              ],
              annotations: [
                { id: instanceId, type: 'AnnotationType_ZoneTransfer', details: [{ key: 'category', valueString: ['Draw'] }], affectedIds: [instanceId] },
              ],
            },
          },
        ],
      },
    });

    collector.collect(makeMsg(801, 10001, 1) as Record<string, unknown>, 'match-8');
    collector.collect(makeMsg(802, 10002, 2) as Record<string, unknown>, 'match-8');

    const records = collector.drawRecords();
    expect(records).toHaveLength(2);

    const g1 = records.find((r) => r.gameNumber === 1);
    const g2 = records.find((r) => r.gameNumber === 2);
    expect(g1?.drawnGrpIds).toEqual([10001]);
    expect(g2?.drawnGrpIds).toEqual([10002]);
  });
});

// ---------------------------------------------------------------------------
// Integration tests: parseAllLogsWithDebug exposes turnDrawRecords
// ---------------------------------------------------------------------------

describe('parseAllLogsWithDebug draw tracking', () => {
  it('exposes turnDrawRecords as an empty array when no GRE messages present', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine('match-no-gre'),
      matchEndLine('match-no-gre', 1),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { turnDrawRecords } = await parseAllLogsWithDebug({ logDir: dir });

    expect(Array.isArray(turnDrawRecords)).toBe(true);
    expect(turnDrawRecords).toHaveLength(0);
  });

  it('returns draw records for completed matches', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine('match-draws'),
      greDrawLine({
        matchId: 'match-draws',
        gameNumber: 1,
        turnNumber: 1,
        localSeatId: 1,
        draws: [{ instanceId: 101, grpId: 5001, ownerSeatId: 1 }],
      }),
      matchEndLine('match-draws', 1),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { turnDrawRecords } = await parseAllLogsWithDebug({ logDir: dir });

    expect(turnDrawRecords).toHaveLength(1);
    expect(turnDrawRecords[0]).toMatchObject({
      matchId: 'match-draws',
      gameNumber: 1,
      turnNumber: 1,
      drawnGrpIds: [5001],
    });
  });

  it('filters out draw records for incomplete (no matchResult) matches', async () => {
    const dir = await makeTempDir();
    // Match start + GRE draw message, but NO match end → matchResult stays null → filtered out
    const lines = [
      matchStartLine('match-incomplete'),
      greDrawLine({
        matchId: 'match-incomplete',
        gameNumber: 1,
        turnNumber: 1,
        localSeatId: 1,
        draws: [{ instanceId: 201, grpId: 7001, ownerSeatId: 1 }],
      }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { turnDrawRecords } = await parseAllLogsWithDebug({ logDir: dir });

    expect(turnDrawRecords).toHaveLength(0);
  });

  it('accumulates draws across multiple turns in the same game', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine('match-multi-turn'),
      greDrawLine({
        matchId: 'match-multi-turn',
        gameNumber: 1,
        turnNumber: 1,
        localSeatId: 1,
        draws: [{ instanceId: 301, grpId: 8001, ownerSeatId: 1 }],
      }),
      greDrawLine({
        matchId: 'match-multi-turn',
        gameNumber: 1,
        turnNumber: 3,
        localSeatId: 1,
        draws: [{ instanceId: 302, grpId: 8002, ownerSeatId: 1 }],
      }),
      matchEndLine('match-multi-turn', 1),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { turnDrawRecords } = await parseAllLogsWithDebug({ logDir: dir });

    expect(turnDrawRecords).toHaveLength(2);

    const t1 = turnDrawRecords.find((r) => r.turnNumber === 1);
    const t3 = turnDrawRecords.find((r) => r.turnNumber === 3);
    expect(t1?.drawnGrpIds).toEqual([8001]);
    expect(t3?.drawnGrpIds).toEqual([8002]);
  });
});
