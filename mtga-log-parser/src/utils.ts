import type { CardEntry, GameResult, MatchResult } from './types.js';

export function gameKey(matchId: string, gameNumber: number): string {
  return `${matchId}:${gameNumber}`;
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
  try {
    return JSON.parse(line.slice(start));
  } catch {
    onError?.();
    return null;
  }
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
