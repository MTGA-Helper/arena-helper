import type { DeckList, Session  } from './types.js';
import { tryParseJSON, toEntries } from './utils.js';

// Populate deckByEvent from a bulk Courses dump (emitted at session start).
function applyCoursesPayload(
  courses: unknown[],
  deckByEvent: Map<string, { name: string; deck: DeckList }>,
): void {
  for (const course of courses) {
    const c = course as Record<string, unknown>;
    const eventName = c.InternalEventName;
    const summary = c.CourseDeckSummary as Record<string, unknown> | undefined;
    const courseDeck = c.CourseDeck as Record<string, unknown> | undefined;
    if (typeof eventName !== 'string' || !summary) continue;
    const name = summary.Name;
    if (typeof name !== 'string' || name.startsWith('?=?')) continue;
    const rawMain = courseDeck?.MainDeck as Array<Record<string, unknown>> | undefined;
    const rawSide = courseDeck?.Sideboard as Array<Record<string, unknown>> | undefined;
    deckByEvent.set(eventName, { name, deck: { main: toEntries(rawMain), sideboard: toEntries(rawSide) } });
  }
}

// Extract deck name and full card list from an EventSetDeckV2 response line/object.
// The event name varies by queue (Traditional_Ladder, Play, Constructed_BestOf3, etc.) — we
// detect by structure, not by event name.
export function extractDeckInfo(obj: Record<string, unknown>): { name: string; deck: DeckList } | null {
  // Direct structure: { InternalEventName, CourseDeckSummary: { Name }, CourseDeck: { MainDeck, Sideboard } }
  const summary = obj.CourseDeckSummary as Record<string, unknown> | undefined;
  if (summary && typeof summary.Name === 'string') {
    const name = summary.Name;
    const courseDeck = obj.CourseDeck as Record<string, unknown> | undefined;
    const rawMain = courseDeck?.MainDeck as Array<Record<string, unknown>> | undefined;
    const rawSide = courseDeck?.Sideboard as Array<Record<string, unknown>> | undefined;
    return { name, deck: { main: toEntries(rawMain), sideboard: toEntries(rawSide) } };
  }

  // Nested in request string: { request: '{"Summary":{"Name":"..."}}' }
  const request = obj.request;
  if (typeof request === 'string') {
    try {
      const inner = JSON.parse(request) as Record<string, unknown>;
      const s = inner.Summary as Record<string, unknown> | undefined;
      if (typeof s?.Name === 'string') return { name: s.Name, deck: { main: [], sideboard: [] } };
    } catch {
      // not JSON
    }
  }
  return null;
}

export function handleParseDeck(line: string, session: Session, onError?: () => void) {
  const obj = tryParseJSON(line, onError);
  if (!obj || typeof obj !== 'object') return;
  const raw = obj as Record<string, unknown>;

  // Bulk Courses dump: emitted at session start, one entry per event queue
  if (Array.isArray(raw.Courses)) applyCoursesPayload(raw.Courses, session.deckByEvent);

  // Individual EventSetDeckV2 / single-course CourseDeckSummary event
  const info = extractDeckInfo(raw);
  if (info) {
    session.pendingDeckName = info.name;
    session.pendingDeckList = info.deck;
    const eventName = raw.InternalEventName;
    if (typeof eventName === 'string') session.deckByEvent.set(eventName, { name: info.name, deck: info.deck });
  }
}
