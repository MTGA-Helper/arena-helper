import { describe, it, expect } from 'vitest';
import { createBoardStateCollector } from '../boardStateParser.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMsg(opts: {
  gameNumber: number;
  turnNumber: number;
  localSeatId: number;
  gameStateType?: string;
  gameObjects?: Record<string, unknown>[];
  annotations?: Record<string, unknown>[];
  zones?: Record<string, unknown>[];
}): Record<string, unknown> {
  const {
    gameNumber,
    turnNumber,
    localSeatId,
    gameStateType = 'GameStateType_Diff',
    gameObjects = [],
    annotations = [],
    zones = [],
  } = opts;

  return {
    greToClientEvent: {
      greToClientMessages: [
        {
          type: 'GREMessageType_GameStateMessage',
          systemSeatIds: [localSeatId],
          gameStateMessage: {
            type: gameStateType,
            gameInfo: { gameNumber },
            turnInfo: { turnNumber, activePlayer: localSeatId },
            gameObjects,
            annotations,
            zones,
          },
        },
      ],
    },
  };
}

// ---------------------------------------------------------------------------
// Tap / untap tracking tests
// ---------------------------------------------------------------------------

describe('createBoardStateCollector tap tracking', () => {
  it('marks a permanent as tapped when isTapped:true appears in a diff game object', () => {
    const collector = createBoardStateCollector();

    // First message: introduce instanceId 100 as an untapped permanent on the battlefield.
    const initMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameStateType: 'GameStateType_Full',
      gameObjects: [
        {
          instanceId: 100,
          grpId: 9000,
          ownerSeatId: 1,
          controllerSeatId: 1,
          type: 'GameObjectType_Card',
          zoneId: 50,
          isTapped: false,
        },
      ],
      zones: [
        { zoneId: 50, type: 'ZoneType_Battlefield', objectInstanceIds: [100] },
      ],
    });

    // Second message: tap event — isTapped:true in the diff game object.
    const tapMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameObjects: [
        {
          instanceId: 100,
          isTapped: true,
        },
      ],
    });

    collector.collect(initMsg, 'match-tap');
    collector.collect(tapMsg, 'match-tap');

    const raw = collector.rawState('match-tap', 1);
    const obj = raw?.gameObjects.find((o) => o.instanceId === 100);
    expect(obj?.isTapped).toBe(true);
  });

  it('marks a permanent as untapped via TappedUntappedPermanent annotation with valueInt32:[0], no isTapped field in diff', () => {
    const collector = createBoardStateCollector();

    // Step 1: introduce instanceId 100 on the battlefield without any tap state.
    const initMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameStateType: 'GameStateType_Full',
      gameObjects: [
        {
          instanceId: 100,
          grpId: 9000,
          ownerSeatId: 1,
          controllerSeatId: 1,
          type: 'GameObjectType_Card',
          zoneId: 50,
          isTapped: false,
        },
      ],
      zones: [
        { zoneId: 50, type: 'ZoneType_Battlefield', objectInstanceIds: [100] },
      ],
    });

    // Step 2: tap the permanent — isTapped:true arrives in the diff game object.
    const tapMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameObjects: [{ instanceId: 100, isTapped: true }],
    });

    // Step 3: untap event — MTGA sends TappedUntappedPermanent annotation with valueInt32:[0]
    // but does NOT include isTapped in the diff game object.
    const untapMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 3,
      localSeatId: 1,
      // No gameObjects entry for instanceId 100 — isTapped is absent from the delta.
      gameObjects: [],
      annotations: [
        {
          id: 999,
          type: 'AnnotationType_TappedUntappedPermanent',
          affectedIds: [100],
          details: [{ key: 'tapped', valueInt32: [0] }],
        },
      ],
    });

    collector.collect(initMsg, 'match-untap');
    collector.collect(tapMsg, 'match-untap');
    collector.collect(untapMsg, 'match-untap');

    const raw = collector.rawState('match-untap', 1);
    const obj = raw?.gameObjects.find((o) => o.instanceId === 100);
    expect(obj?.isTapped).toBe(false);
  });

  it('also handles tap event via TappedUntappedPermanent annotation with valueInt32:[1]', () => {
    const collector = createBoardStateCollector();

    // Introduce the card untapped.
    const initMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameStateType: 'GameStateType_Full',
      gameObjects: [
        {
          instanceId: 200,
          grpId: 8888,
          ownerSeatId: 1,
          controllerSeatId: 1,
          type: 'GameObjectType_Card',
          zoneId: 50,
          isTapped: false,
        },
      ],
      zones: [
        { zoneId: 50, type: 'ZoneType_Battlefield', objectInstanceIds: [200] },
      ],
    });

    // Tap via annotation only (no isTapped in game object).
    const tapViaAnnotation = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameObjects: [],
      annotations: [
        {
          id: 1001,
          type: 'AnnotationType_TappedUntappedPermanent',
          affectedIds: [200],
          details: [{ key: 'tapped', valueInt32: [1] }],
        },
      ],
    });

    collector.collect(initMsg, 'match-tapann');
    collector.collect(tapViaAnnotation, 'match-tapann');

    const raw = collector.rawState('match-tapann', 1);
    const obj = raw?.gameObjects.find((o) => o.instanceId === 200);
    expect(obj?.isTapped).toBe(true);
  });

  it('ignores TappedUntappedPermanent annotations for unknown instanceIds', () => {
    const collector = createBoardStateCollector();

    // No game objects introduced — instanceId 999 is unknown.
    const initMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameStateType: 'GameStateType_Full',
      gameObjects: [],
    });

    const untapUnknown = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameObjects: [],
      annotations: [
        {
          id: 2000,
          type: 'AnnotationType_TappedUntappedPermanent',
          affectedIds: [999],
          details: [{ key: 'tapped', valueInt32: [0] }],
        },
      ],
    });

    collector.collect(initMsg, 'match-unknown');
    // Should not throw.
    collector.collect(untapUnknown, 'match-unknown');

    const raw = collector.rawState('match-unknown', 1);
    // instanceId 999 was never in the map — should still not be present.
    const obj = raw?.gameObjects.find((o) => o.instanceId === 999);
    expect(obj).toBeUndefined();
  });

  it('ignores TappedUntappedPermanent annotations with invalid or missing valueInt32', () => {
    const collector = createBoardStateCollector();

    const initMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameStateType: 'GameStateType_Full',
      gameObjects: [
        {
          instanceId: 300,
          grpId: 7777,
          ownerSeatId: 1,
          controllerSeatId: 1,
          type: 'GameObjectType_Card',
          zoneId: 50,
          isTapped: true,
        },
      ],
      zones: [
        { zoneId: 50, type: 'ZoneType_Battlefield', objectInstanceIds: [300] },
      ],
    });

    // Annotation with missing valueInt32 — should be a no-op.
    const badAnnotation = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameObjects: [],
      annotations: [
        {
          id: 3000,
          type: 'AnnotationType_TappedUntappedPermanent',
          affectedIds: [300],
          details: [{ key: 'tapped' }], // no valueInt32
        },
      ],
    });

    collector.collect(initMsg, 'match-badann');
    collector.collect(badAnnotation, 'match-badann');

    const raw = collector.rawState('match-badann', 1);
    const obj = raw?.gameObjects.find((o) => o.instanceId === 300);
    // isTapped should remain true (unchanged) since the annotation had no valid valueInt32.
    expect(obj?.isTapped).toBe(true);
  });

  it('battlefield snapshot reflects untapped state after TappedUntappedPermanent annotation', () => {
    const collector = createBoardStateCollector();

    // Full state: introduce the card on the battlefield.
    const initMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameStateType: 'GameStateType_Full',
      gameObjects: [
        {
          instanceId: 100,
          grpId: 9000,
          ownerSeatId: 1,
          controllerSeatId: 1,
          type: 'GameObjectType_Card',
          zoneId: 50,
          isTapped: false,
        },
      ],
      zones: [
        { zoneId: 50, type: 'ZoneType_Battlefield', objectInstanceIds: [100] },
      ],
    });

    // Tap via game object diff.
    const tapMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 1,
      localSeatId: 1,
      gameObjects: [{ instanceId: 100, isTapped: true }],
    });

    // Untap via annotation only (no isTapped in game object diff).
    const untapMsg = makeMsg({
      gameNumber: 1,
      turnNumber: 3,
      localSeatId: 1,
      gameObjects: [],
      annotations: [
        {
          id: 999,
          type: 'AnnotationType_TappedUntappedPermanent',
          affectedIds: [100],
          details: [{ key: 'tapped', valueInt32: [0] }],
        },
      ],
    });

    collector.collect(initMsg, 'match-snap');
    collector.collect(tapMsg, 'match-snap');
    collector.collect(untapMsg, 'match-snap');

    // Find the last snapshot for turn 3 to check board state after untap.
    const snapshots = collector.snapshots();
    const turn3Snaps = snapshots.filter((s) => s.turnNumber === 3);
    expect(turn3Snaps.length).toBeGreaterThan(0);

    const lastSnap = turn3Snaps[turn3Snaps.length - 1];
    const card = lastSnap.myBattlefield.find((c) => c.instanceId === 100);
    expect(card).toBeDefined();
    expect(card?.isTapped).toBe(false);
  });
});
