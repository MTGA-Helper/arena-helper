import type { Match } from './types.js';

/**
 * Returns a count of matches played against each opponent platform.
 * The platform string comes directly from the MTGA log (e.g. "Mac", "Windows", "iOS", "Android").
 * Matches where the platform was not recorded are grouped under "Unknown".
 */
export function opponentsByPlatform(matches: Match[]): Record<string, number> {
  const result: Record<string, number> = {};
  for (const match of matches) {
    const platform = match.opponentPlatform || 'Unknown';
    result[platform] = (result[platform] ?? 0) + 1;
  }
  return result;
}
