import type { CardEntry, GameResult, MatchResult } from './types.js';

export function gameKey(matchId: string, gameNumber: number): string {
  return `${matchId}:${gameNumber}`;
}

export function isDrawReason(reason: string): boolean {
  return reason.toLowerCase().endsWith('draw');
}

export function computeMatchResult(g1: GameResult, g2: GameResult, g3: GameResult): MatchResult {
  if (g1 === null) return null;

  const results = [g1, g2, g3].filter((g) => g !== null) as (1 | 0 | 'Draw')[];
  const wins = results.filter((g) => g === 1).length;
  const losses = results.filter((g) => g === 0).length;

  if (wins >= 2) return 'Win';
  if (losses >= 2) return 'Loss';
  if (results.includes('Draw')) {
    if (wins === 1 && losses === 0) return 'Win';
    if (losses === 1 && wins === 0) return 'Loss';
    return 'Draw';
  }
  // Match ended early (opponent timeout or forfeit before accumulating 2 wins/losses).
  if (wins > losses) return 'Win';
  if (losses > wins) return 'Loss';
  return null;
}

export function parseLogDate(filename: string): number {
  const match = filename.match(/(\d{2})-(\d{2})-(\d{4}) (\d{2})\.(\d{2})\.(\d{2})/);
  if (!match) return Infinity;
  const [, mm, dd, yyyy, hh, min, ss] = match;
  return new Date(`${yyyy}-${mm}-${dd}T${hh}:${min}:${ss}Z`).getTime();
}

export function tryParseJSON(line: string, onError?: () => void): unknown {
  const start = line.indexOf('{');
  if (start === -1) return null;
  const candidate = line.slice(start);
  try {
    return JSON.parse(candidate);
  } catch {
    // MTGA sometimes logs a diagnostic line (e.g. "Couldn't find affector id ...") right after
    // a JSON entry; retry with only the first balanced object so those events aren't lost.
    const end = findJsonObjectEnd(candidate);
    if (end !== -1 && end < candidate.length) {
      try {
        return JSON.parse(candidate.slice(0, end));
      } catch {
        // fall through to the error handler
      }
    }
    onError?.();
    return null;
  }
}

function findJsonObjectEnd(text: string): number {
  let depth = 0;
  let inString = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inString) {
      if (ch === '\\') i++;
      else if (ch === '"') inString = false;
    } else if (ch === '"') {
      inString = true;
    } else if (ch === '{') {
      depth++;
    } else if (ch === '}' && --depth === 0) {
      return i + 1;
    }
  }
  return -1;
}

export function isGameStateMessage(msg: Record<string, unknown>): boolean {
  return msg.type === 'GREMessageType_GameStateMessage'
    || msg.type === 'GREMessageType_QueuedGameStateMessage';
}

export function toEntries(arr: Array<Record<string, unknown>> | undefined): CardEntry[] {
  return (arr ?? []).flatMap((card) => {
    const cardId = card.cardId;
    const quantity = card.quantity;
    if (typeof cardId !== 'number' || typeof quantity !== 'number') return [];
    return [{ cardId, quantity }];
  });
}
