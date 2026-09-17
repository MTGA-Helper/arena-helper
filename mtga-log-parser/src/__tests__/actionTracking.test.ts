import { describe, it, expect, afterEach } from 'vitest';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseAllLogsWithDebug } from '../logParser.js';
import { createBoardStateCollector } from '../boardStateParser.js';

// ---------------------------------------------------------------------------
// Fixture helpers
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
 * - the source game object for the action
 * - a ZoneTransfer annotation with an action category (CastSpell, ActivateAbility, TriggerAbility)
 * - optionally, target game objects and AnnotationType_Targetted annotations
 */
function greActionLine(opts: {
  matchId: string;
  gameNumber: number;
  turnNumber: number;
  localSeatId: number;
  activePlayer?: number;
  category: 'CastSpell' | 'ActivateAbility' | 'TriggerAbility';
  source: { instanceId: number; grpId: number; ownerSeatId: number };
  targets?: Array<{ instanceId: number; grpId: number }>;
  gameStateType?: string;
}): string {
  const { gameNumber, turnNumber, localSeatId, category, source, targets = [], gameStateType = 'GameStateType_Diff' } = opts;
  const activePlayer = opts.activePlayer ?? localSeatId;

  const gameObjects: Array<Record<string, unknown>> = [
    {
      instanceId: source.instanceId,
      grpId: source.grpId,
      ownerSeatId: source.ownerSeatId,
      controllerSeatId: source.ownerSeatId,
      type: 'GameObjectType_Card',
      zoneId: 7, // stack zone
    },
    ...targets.map((t) => ({
      instanceId: t.instanceId,
      grpId: t.grpId,
      ownerSeatId: localSeatId,
      controllerSeatId: localSeatId,
      type: 'GameObjectType_Card',
      zoneId: 1, // battlefield
    })),
  ];

  const annotations: Array<Record<string, unknown>> = [
    {
      id: 2000,
      type: 'AnnotationType_ZoneTransfer',
      details: [{ key: 'category', valueString: [category] }],
      affectedIds: [source.instanceId],
    },
  ];

  // Targeting data lives in persistentAnnotations using AnnotationType_TargetSpec and affectorId.
  // Each target gets its own entry (affectedIds can also be an array of multiple targets).
  const persistentAnnotations: Array<Record<string, unknown>> = targets.map((t, i) => ({
    id: 3000 + i,
    affectorId: source.instanceId,
    affectedIds: [t.instanceId],
    type: ['AnnotationType_TargetSpec'],
    details: [
      { key: 'abilityGrpId', valueInt32: [source.grpId] },
      { key: 'index', valueInt32: [i + 1] },
    ],
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
            ...(persistentAnnotations.length > 0 ? { persistentAnnotations } : {}),
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
  const dir = await mkdtemp(join(tmpdir(), 'mtga-action-test-'));
  tempDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(tempDirs.splice(0).map((d) => rm(d, { recursive: true, force: true })));
});

// ---------------------------------------------------------------------------
// Unit tests for createBoardStateCollector action tracking
// ---------------------------------------------------------------------------

describe('createBoardStateCollector action tracking', () => {
  it('records a CastSpell action on turn 1 with correct fields', () => {
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
                { instanceId: 101, grpId: 5001, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 7 },
              ],
              annotations: [
                {
                  id: 1,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [101],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-1');

    const records = collector.actionRecords();
    expect(records).toHaveLength(1);
    expect(records[0]).toMatchObject({
      matchId: 'match-1',
      gameNumber: 1,
      turnNumber: 1,
      type: 'CastSpell',
      castByMe: true,
      sourceGrpId: 5001,
      sourceInstanceId: 101,
      targetInstanceIds: [],
      targetGrpIds: [],
    });
  });

  it('records ActivateAbility and TriggerAbility categories correctly', () => {
    const collector = createBoardStateCollector();

    const makeMsg = (instanceId: number, grpId: number, category: string) => ({
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 2, activePlayer: 1 },
              gameObjects: [
                { instanceId, grpId, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 1 },
              ],
              annotations: [
                {
                  id: instanceId,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: [category] }],
                  affectedIds: [instanceId],
                },
              ],
            },
          },
        ],
      },
    });

    collector.collect(makeMsg(201, 6001, 'ActivateAbility') as Record<string, unknown>, 'match-cats');
    collector.collect(makeMsg(202, 6002, 'TriggerAbility') as Record<string, unknown>, 'match-cats');

    const records = collector.actionRecords();
    expect(records).toHaveLength(2);

    const activate = records.find((r) => r.type === 'ActivateAbility');
    const trigger = records.find((r) => r.type === 'TriggerAbility');
    expect(activate).toBeDefined();
    expect(activate?.sourceGrpId).toBe(6001);
    expect(trigger).toBeDefined();
    expect(trigger?.sourceGrpId).toBe(6002);
  });

  it('ignores turn-0 annotations', () => {
    const collector = createBoardStateCollector();

    const msg = {
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
                { instanceId: 301, grpId: 7001, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 7 },
              ],
              annotations: [
                {
                  id: 1,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [301],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-turn0');

    expect(collector.actionRecords()).toHaveLength(0);
  });

  it('skips actions where sourceGrpId is 0 or the instanceId is not in gameObjects', () => {
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
                // grpId is 0 — not resolvable
                { instanceId: 401, grpId: 0, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card' },
              ],
              annotations: [
                // instanceId 402 not in gameObjects
                {
                  id: 1,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [402],
                },
                // grpId is 0
                {
                  id: 2,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [401],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-skip');

    expect(collector.actionRecords()).toHaveLength(0);
  });

  it('attaches target grpIds from AnnotationType_TargetSpec persistentAnnotations', () => {
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
                // source spell on stack
                { instanceId: 500, grpId: 8000, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 7 },
                // target creature on battlefield
                { instanceId: 501, grpId: 8001, ownerSeatId: 2, controllerSeatId: 2, type: 'GameObjectType_Card', zoneId: 1 },
              ],
              annotations: [
                {
                  id: 1,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [500],
                },
              ],
              persistentAnnotations: [
                {
                  id: 2,
                  affectorId: 500,
                  affectedIds: [501],
                  type: ['AnnotationType_TargetSpec'],
                  details: [{ key: 'abilityGrpId', valueInt32: [8000] }],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-target');

    const records = collector.actionRecords();
    expect(records).toHaveLength(1);
    expect(records[0].sourceGrpId).toBe(8000);
    expect(records[0].targetInstanceIds).toEqual([501]);
    expect(records[0].targetGrpIds).toEqual([8001]);
  });

  it('attaches multiple targets correctly', () => {
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
              turnInfo: { turnNumber: 5, activePlayer: 1 },
              gameObjects: [
                { instanceId: 600, grpId: 9000, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 7 },
                { instanceId: 601, grpId: 9001, ownerSeatId: 2, controllerSeatId: 2, type: 'GameObjectType_Card', zoneId: 1 },
                { instanceId: 602, grpId: 9002, ownerSeatId: 2, controllerSeatId: 2, type: 'GameObjectType_Card', zoneId: 1 },
              ],
              annotations: [
                {
                  id: 1,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [600],
                },
              ],
              persistentAnnotations: [
                {
                  id: 2,
                  affectorId: 600,
                  affectedIds: [601],
                  type: ['AnnotationType_TargetSpec'],
                  details: [{ key: 'abilityGrpId', valueInt32: [9000] }],
                },
                {
                  id: 3,
                  affectorId: 600,
                  affectedIds: [602],
                  type: ['AnnotationType_TargetSpec'],
                  details: [{ key: 'abilityGrpId', valueInt32: [9000] }],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-multitarget');

    const records = collector.actionRecords();
    expect(records).toHaveLength(1);
    expect(records[0].targetInstanceIds).toEqual([601, 602]);
    expect(records[0].targetGrpIds).toEqual([9001, 9002]);
  });

  it('records castByMe=false for opponent actions', () => {
    const collector = createBoardStateCollector();

    const msg = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1], // local seat is 1
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 2, activePlayer: 2 },
              gameObjects: [
                // opponent's card (ownerSeatId=2, localSeatId=1)
                { instanceId: 700, grpId: 10000, ownerSeatId: 2, controllerSeatId: 2, type: 'GameObjectType_Card', zoneId: 7 },
              ],
              annotations: [
                {
                  id: 1,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [700],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-opp');

    const records = collector.actionRecords();
    expect(records).toHaveLength(1);
    expect(records[0].castByMe).toBe(false);
    expect(records[0].sourceGrpId).toBe(10000);
  });

  it('confirms Draw annotations do NOT appear in actionRecords', () => {
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
                { instanceId: 800, grpId: 11000, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 10 },
              ],
              annotations: [
                {
                  id: 1,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['Draw'] }],
                  affectedIds: [800],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msg as Record<string, unknown>, 'match-draw-check');

    // Draw annotation should show in drawRecords, not actionRecords
    expect(collector.drawRecords()).toHaveLength(1);
    expect(collector.actionRecords()).toHaveLength(0);
  });

  // ---------------------------------------------------------------------------
  // Regression test for GitHub issue #3:
  // ZoneTransfer and Targetted annotations arriving in SEPARATE GRE messages
  // ---------------------------------------------------------------------------

  it('attaches targets when ZoneTransfer and TargetSpec arrive in separate messages (same collect call)', () => {
    // This is the core regression for issue #3. Before the fix, pendingActions was scoped
    // per-message: message A's ZoneTransfer would populate pendingActions, which then went
    // out of scope before message B's TargetSpec annotation ran Pass 2, so targetInstanceIds
    // was always [].
    const collector = createBoardStateCollector();

    const msgA = {
      greToClientEvent: {
        greToClientMessages: [
          {
            // Message A: ZoneTransfer (CastSpell) — source game object + action stub
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 4, activePlayer: 1 },
              gameObjects: [
                { instanceId: 900, grpId: 12000, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 7 },
              ],
              annotations: [
                {
                  id: 10,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [900],
                },
              ],
            },
          },
          {
            // Message B (same GRE batch): TargetSpec in persistentAnnotations — target game object
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 4, activePlayer: 1 },
              gameObjects: [
                { instanceId: 901, grpId: 12001, ownerSeatId: 2, controllerSeatId: 2, type: 'GameObjectType_Card', zoneId: 1 },
              ],
              persistentAnnotations: [
                {
                  id: 11,
                  affectorId: 900,
                  affectedIds: [901],
                  type: ['AnnotationType_TargetSpec'],
                  details: [{ key: 'abilityGrpId', valueInt32: [12000] }],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(msgA as Record<string, unknown>, 'match-cross-msg');

    const records = collector.actionRecords();
    expect(records).toHaveLength(1);
    expect(records[0].sourceGrpId).toBe(12000);
    expect(records[0].sourceInstanceId).toBe(900);
    expect(records[0].targetInstanceIds).toEqual([901]);
    expect(records[0].targetGrpIds).toEqual([12001]);
  });

  it('attaches targets when ZoneTransfer and TargetSpec arrive in separate collect() calls (separate GRE event batches)', () => {
    // This tests the cross-collect-call case: message with ZoneTransfer is in one
    // greToClientEvent batch, message with TargetSpec is in the next batch.
    // Before the fix, pendingActions was re-created each collect() call so the second
    // batch's Pass 2 always found an empty map.
    const collector = createBoardStateCollector();

    // Batch 1: ZoneTransfer only
    const batch1 = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 6, activePlayer: 1 },
              gameObjects: [
                { instanceId: 950, grpId: 13000, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 7 },
              ],
              annotations: [
                {
                  id: 20,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [950],
                },
              ],
            },
          },
        ],
      },
    };

    // Batch 2: AnnotationType_TargetSpec in persistentAnnotations (separate greToClientEvent)
    const batch2 = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 6, activePlayer: 1 },
              gameObjects: [
                { instanceId: 951, grpId: 13001, ownerSeatId: 2, controllerSeatId: 2, type: 'GameObjectType_Card', zoneId: 1 },
              ],
              persistentAnnotations: [
                {
                  id: 21,
                  affectorId: 950,
                  affectedIds: [951],
                  type: ['AnnotationType_TargetSpec'],
                  details: [{ key: 'abilityGrpId', valueInt32: [13000] }],
                },
              ],
            },
          },
        ],
      },
    };

    collector.collect(batch1 as Record<string, unknown>, 'match-cross-call');
    collector.collect(batch2 as Record<string, unknown>, 'match-cross-call');

    const records = collector.actionRecords();
    expect(records).toHaveLength(1);
    expect(records[0].sourceGrpId).toBe(13000);
    expect(records[0].sourceInstanceId).toBe(950);
    expect(records[0].targetInstanceIds).toEqual([951]);
    expect(records[0].targetGrpIds).toEqual([13001]);
  });

  it('flushes prior turn pending actions (without targets) when turn advances', () => {
    // An untargeted spell cast on turn 7 should appear in actionRecords with empty targets
    // when turn 8 is processed (the turn-change flush).
    const collector = createBoardStateCollector();

    // Turn 7: CastSpell with no Targetted annotation
    const turn7 = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 7, activePlayer: 1 },
              gameObjects: [
                { instanceId: 960, grpId: 14000, ownerSeatId: 1, controllerSeatId: 1, type: 'GameObjectType_Card', zoneId: 7 },
              ],
              annotations: [
                {
                  id: 30,
                  type: 'AnnotationType_ZoneTransfer',
                  details: [{ key: 'category', valueString: ['CastSpell'] }],
                  affectedIds: [960],
                },
              ],
            },
          },
        ],
      },
    };

    // Turn 8: unrelated message that advances the turn number
    const turn8 = {
      greToClientEvent: {
        greToClientMessages: [
          {
            type: 'GREMessageType_GameStateMessage',
            systemSeatIds: [1],
            gameStateMessage: {
              type: 'GameStateType_Diff',
              gameInfo: { gameNumber: 1 },
              turnInfo: { turnNumber: 8, activePlayer: 2 },
              gameObjects: [],
              annotations: [],
            },
          },
        ],
      },
    };

    collector.collect(turn7 as Record<string, unknown>, 'match-turn-flush');
    collector.collect(turn8 as Record<string, unknown>, 'match-turn-flush');

    const records = collector.actionRecords();
    expect(records).toHaveLength(1);
    expect(records[0].turnNumber).toBe(7);
    expect(records[0].sourceGrpId).toBe(14000);
    expect(records[0].targetInstanceIds).toEqual([]);
    expect(records[0].targetGrpIds).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Integration tests: parseAllLogsWithDebug exposes gameActions
// ---------------------------------------------------------------------------

describe('parseAllLogsWithDebug action tracking', () => {
  it('exposes gameActions as an empty array when no GRE messages present', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine('match-no-gre'),
      matchEndLine('match-no-gre', 1),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { gameActions } = await parseAllLogsWithDebug({ logDir: dir });

    expect(Array.isArray(gameActions)).toBe(true);
    expect(gameActions).toHaveLength(0);
  });

  it('returns action records for completed matches', async () => {
    const dir = await makeTempDir();
    const lines = [
      matchStartLine('match-actions'),
      greActionLine({
        matchId: 'match-actions',
        gameNumber: 1,
        turnNumber: 3,
        localSeatId: 1,
        category: 'CastSpell',
        source: { instanceId: 101, grpId: 5001, ownerSeatId: 1 },
      }),
      matchEndLine('match-actions', 1),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { gameActions } = await parseAllLogsWithDebug({ logDir: dir });

    expect(gameActions).toHaveLength(1);
    expect(gameActions[0]).toMatchObject({
      matchId: 'match-actions',
      gameNumber: 1,
      turnNumber: 3,
      type: 'CastSpell',
      castByMe: true,
      sourceGrpId: 5001,
      sourceInstanceId: 101,
    });
  });

  it('filters out action records for incomplete (no matchResult) matches', async () => {
    const dir = await makeTempDir();
    // Match start + GRE action message, but NO match end → matchResult stays null → filtered out
    const lines = [
      matchStartLine('match-incomplete'),
      greActionLine({
        matchId: 'match-incomplete',
        gameNumber: 1,
        turnNumber: 1,
        localSeatId: 1,
        category: 'CastSpell',
        source: { instanceId: 201, grpId: 7001, ownerSeatId: 1 },
      }),
    ];
    await writeFile(join(dir, logFilename()), lines.join('\n'));

    const { gameActions } = await parseAllLogsWithDebug({ logDir: dir });

    expect(gameActions).toHaveLength(0);
  });
});
