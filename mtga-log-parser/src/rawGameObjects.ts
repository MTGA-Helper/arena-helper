import type { BoardCard, RawPlayer, RawGameObject, RawZone } from './types.js';

export function toGameObject(raw: Record<string, unknown>): RawGameObject | null {
  const instanceId = raw.instanceId;
  if (typeof instanceId !== 'number') return null;

  const grpId = typeof raw.grpId === 'number' ? raw.grpId : undefined;
  const ownerSeatId = typeof raw.ownerSeatId === 'number' ? raw.ownerSeatId : undefined;
  const controllerSeatId = typeof raw.controllerSeatId === 'number' ? raw.controllerSeatId : undefined;
  const type = typeof raw.type === 'string' ? raw.type : undefined;
  const power = typeof raw.power === 'number' ? raw.power : undefined;
  const toughness = typeof raw.toughness === 'number' ? raw.toughness : undefined;
  const zoneId = typeof raw.zoneId === 'number' ? raw.zoneId : undefined;

  // isTapped: check direct boolean field or status string
  let isTapped = false;
  if (typeof raw.isTapped === 'boolean') {
    isTapped = raw.isTapped;
  } else if (typeof raw.status === 'string') {
    isTapped = raw.status === 'StatusType_Tapped';
  }

  // counters: object mapping counter type string to number
  let counters: Record<string, number> | undefined;
  if (raw.counters && typeof raw.counters === 'object' && !Array.isArray(raw.counters)) {
    const rawCounters = raw.counters as Record<string, unknown>;
    const built: Record<string, number> = {};
    for (const [k, v] of Object.entries(rawCounters)) {
      if (typeof v === 'number') built[k] = v;
    }
    if (Object.keys(built).length > 0) counters = built;
  }

  return { instanceId, grpId, ownerSeatId, controllerSeatId, type, power, toughness, zoneId, isTapped, counters };
}

// Merge a delta game object update into an existing entry.
// Only overwrite fields that are explicitly present in the raw delta — absent fields keep
// their existing values. This prevents delta messages (e.g. {instanceId, isTapped:true})
// from wiping out zoneId, grpId, controllerSeatId, and other fields not in the delta.
export function mergeGameObject(
  existing: RawGameObject,
  raw: Record<string, unknown>,
  parsed: RawGameObject,
): RawGameObject {
  const tapExplicit = 'isTapped' in raw || 'status' in raw;
  return {
    instanceId: parsed.instanceId,
    grpId: parsed.grpId ?? existing.grpId,
    ownerSeatId: parsed.ownerSeatId ?? existing.ownerSeatId,
    controllerSeatId: parsed.controllerSeatId ?? existing.controllerSeatId,
    type: parsed.type ?? existing.type,
    power: parsed.power ?? existing.power,
    toughness: parsed.toughness ?? existing.toughness,
    zoneId: parsed.zoneId ?? existing.zoneId,
    isTapped: tapExplicit ? parsed.isTapped : existing.isTapped,
    counters: parsed.counters ?? existing.counters,
  };
}

export function toZone(raw: Record<string, unknown>): RawZone | null {
  const zoneId = raw.zoneId;
  if (typeof zoneId !== 'number') return null;

  const type = typeof raw.type === 'string' ? raw.type : undefined;
  const ownerSeatId = typeof raw.ownerSeatId === 'number' ? raw.ownerSeatId : undefined;
  const objectInstanceIds = Array.isArray(raw.objectInstanceIds)
    ? (raw.objectInstanceIds as unknown[]).filter((x): x is number => typeof x === 'number')
    : undefined;

  return { zoneId, type, ownerSeatId, objectInstanceIds };
}

export function toPlayer(raw: Record<string, unknown>): RawPlayer {
  return {
    systemSeatNumber: typeof raw.systemSeatNumber === 'number' ? raw.systemSeatNumber : undefined,
    lifeTotal: typeof raw.lifeTotal === 'number' ? raw.lifeTotal : undefined,
    turnNumber: typeof raw.turnNumber === 'number' ? raw.turnNumber : undefined,
  };
}

export function toBoardCard(obj: RawGameObject): BoardCard {
  return {
    instanceId: obj.instanceId,
    grpId: obj.grpId ?? 0,
    name: '',  // resolved at endpoint time
    power: obj.power,
    toughness: obj.toughness,
    isTapped: obj.isTapped ?? false,
    counters: obj.counters,
  };
}
