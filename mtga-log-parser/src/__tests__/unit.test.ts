import { describe, it, expect } from 'vitest';
import { computeMatchResult, parseLogDate } from '../utils.js';
import { MatchFilters } from '../logParser.js';
import { extractDeckInfo } from '../deckParser.js';
import { opponentsByPlatform } from '../analytics.js';
import type { Match } from '../types.js';

function makeMatch(partial: Partial<Match> = {}): Match {
  return {
    id: 'test-id',
    timestamp: 0,
    myPlayerId: '',
    opponentPlayerId: '',
    myGamerTag: '',
    opponentGamerTag: '',
    opponent: 'Opponent',
    opponentPlatform: '',
    opponentDeck: '',
    opponentColors: '',
    myDeck: '',
    onPlay: null,
    game1: null,
    game2: null,
    game3: null,
    matchResult: null,
    eventId: '',
    importedAt: 0,
    notes: '',
    ...partial,
  };
}

// ---------------------------------------------------------------------------
// computeMatchResult
// ---------------------------------------------------------------------------

describe('computeMatchResult', () => {
  describe('Bo1 — single game', () => {
    it('returns Win for a single win', () => {
      expect(computeMatchResult(1, null, null)).toBe('Win');
    });

    it('returns Loss for a single loss', () => {
      expect(computeMatchResult(0, null, null)).toBe('Loss');
    });

    it('returns Draw for a single draw', () => {
      expect(computeMatchResult('Draw', null, null)).toBe('Draw');
    });
  });

  describe('Bo3 — two or three games', () => {
    it('returns Win for 2-0', () => {
      expect(computeMatchResult(1, 1, null)).toBe('Win');
    });

    it('returns Loss for 0-2', () => {
      expect(computeMatchResult(0, 0, null)).toBe('Loss');
    });

    it('returns Win for 2-1 (win last)', () => {
      expect(computeMatchResult(1, 0, 1)).toBe('Win');
    });

    it('returns Win for 2-1 (win first)', () => {
      expect(computeMatchResult(0, 1, 1)).toBe('Win');
    });

    it('returns Loss for 1-2 (loss last)', () => {
      expect(computeMatchResult(0, 1, 0)).toBe('Loss');
    });

    it('returns Loss for 1-2 (loss first)', () => {
      expect(computeMatchResult(1, 0, 0)).toBe('Loss');
    });
  });

  describe('draw combinations', () => {
    it('returns Win for Draw + Win', () => {
      expect(computeMatchResult('Draw', 1, null)).toBe('Win');
    });

    it('returns Loss for Draw + Loss', () => {
      expect(computeMatchResult('Draw', 0, null)).toBe('Loss');
    });

    it('returns Draw for two draws', () => {
      expect(computeMatchResult('Draw', 'Draw', null)).toBe('Draw');
    });

    it('returns Win when two wins outweigh a draw', () => {
      expect(computeMatchResult('Draw', 1, 1)).toBe('Win');
    });
  });

  describe('null / incomplete', () => {
    it('returns null when g1 is null (no games played)', () => {
      expect(computeMatchResult(null, null, null)).toBe(null);
    });

    it('returns null for split 1-1 without a deciding game', () => {
      expect(computeMatchResult(1, 0, null)).toBe(null);
    });
  });
});

// ---------------------------------------------------------------------------
// parseLogDate
// ---------------------------------------------------------------------------

describe('parseLogDate', () => {
  it('parses a valid log filename to a UTC ms timestamp', () => {
    const ts = parseLogDate('UTC_Log - 05-04-2026 21.30.00.log');
    expect(ts).toBe(new Date('2026-05-04T21:30:00Z').getTime());
  });

  it('returns Infinity for filenames without a matching date pattern', () => {
    expect(parseLogDate('not-a-log.txt')).toBe(Infinity);
    expect(parseLogDate('')).toBe(Infinity);
  });

  it('sorts older files before newer files', () => {
    const a = parseLogDate('UTC_Log - 01-01-2025 00.00.00.log');
    const b = parseLogDate('UTC_Log - 01-01-2026 00.00.00.log');
    expect(a).toBeLessThan(b);
  });
});

// ---------------------------------------------------------------------------
// extractDeckInfo
// ---------------------------------------------------------------------------

describe('extractDeckInfo', () => {
  it('extracts name and card list from a CourseDeckSummary object', () => {
    const obj = {
      InternalEventName: 'Traditional_Ladder',
      CourseDeckSummary: { Name: 'My Deck' },
      CourseDeck: {
        MainDeck: [{ cardId: 100001, quantity: 4 }, { cardId: 100002, quantity: 2 }],
        Sideboard: [{ cardId: 200001, quantity: 1 }],
      },
    };
    const result = extractDeckInfo(obj);
    expect(result).toEqual({
      name: 'My Deck',
      deck: {
        main: [{ cardId: 100001, quantity: 4 }, { cardId: 100002, quantity: 2 }],
        sideboard: [{ cardId: 200001, quantity: 1 }],
      },
    });
  });

  it('handles missing MainDeck/Sideboard gracefully', () => {
    const obj = {
      CourseDeckSummary: { Name: 'Empty Deck' },
      CourseDeck: {},
    };
    const result = extractDeckInfo(obj);
    expect(result).toEqual({ name: 'Empty Deck', deck: { main: [], sideboard: [] } });
  });

  it('skips card entries with missing or wrong-typed fields', () => {
    const obj = {
      CourseDeckSummary: { Name: 'Partial Deck' },
      CourseDeck: {
        MainDeck: [
          { cardId: 100001, quantity: 4 },
          { cardId: 'bad', quantity: 2 },
          { cardId: 100003 },
        ],
      },
    };
    const result = extractDeckInfo(obj);
    expect(result?.deck.main).toEqual([{ cardId: 100001, quantity: 4 }]);
  });

  it('extracts name from a nested request string', () => {
    const obj = {
      request: JSON.stringify({ Summary: { Name: 'Request Deck' } }),
    };
    const result = extractDeckInfo(obj);
    expect(result).toEqual({ name: 'Request Deck', deck: { main: [], sideboard: [] } });
  });

  it('returns null when neither structure is present', () => {
    expect(extractDeckInfo({})).toBeNull();
    expect(extractDeckInfo({ foo: 'bar' })).toBeNull();
  });

  it('returns null when CourseDeckSummary exists but Name is not a string', () => {
    const obj = { CourseDeckSummary: { Name: 42 } };
    expect(extractDeckInfo(obj)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// MatchFilters
// ---------------------------------------------------------------------------

describe('MatchFilters', () => {
  describe('all', () => {
    it('always returns true regardless of input', () => {
      expect(MatchFilters.all('Traditional_Ladder')).toBe(true);
      expect(MatchFilters.all('')).toBe(true);
      expect(MatchFilters.all('QuickDraft_DOM')).toBe(true);
    });
  });

  describe('constructed', () => {
    it('includes ranked and play queues', () => {
      expect(MatchFilters.constructed('Traditional_Ladder')).toBe(true);
      expect(MatchFilters.constructed('Play')).toBe(true);
      expect(MatchFilters.constructed('PlayRanked')).toBe(true);
      expect(MatchFilters.constructed('Constructed_BestOf3')).toBe(true);
    });

    it('excludes draft events', () => {
      expect(MatchFilters.constructed('QuickDraft_DOM')).toBe(false);
      expect(MatchFilters.constructed('PremierDraft_NEO')).toBe(false);
      expect(MatchFilters.constructed('TradDraft_MKM')).toBe(false);
    });

    it('excludes sealed events', () => {
      expect(MatchFilters.constructed('TradSealed_MOM')).toBe(false);
      expect(MatchFilters.constructed('Sealed_BLB')).toBe(false);
    });

    it('excludes jump-in events', () => {
      expect(MatchFilters.constructed('JumpIn')).toBe(false);
    });

    it('excludes empty string', () => {
      expect(MatchFilters.constructed('')).toBe(false);
    });
  });

  describe('bo3Constructed', () => {
    it('includes Traditional_ prefix events', () => {
      expect(MatchFilters.bo3Constructed('Traditional_Ladder')).toBe(true);
      expect(MatchFilters.bo3Constructed('Traditional_Championship')).toBe(true);
    });

    it('includes Constructed_BestOf3', () => {
      expect(MatchFilters.bo3Constructed('Constructed_BestOf3')).toBe(true);
    });

    it('excludes Bo1 play queues', () => {
      expect(MatchFilters.bo3Constructed('Play')).toBe(false);
      expect(MatchFilters.bo3Constructed('PlayRanked')).toBe(false);
    });

    it('excludes draft and sealed', () => {
      expect(MatchFilters.bo3Constructed('QuickDraft_DOM')).toBe(false);
      expect(MatchFilters.bo3Constructed('TradSealed_MOM')).toBe(false);
    });
  });
});

// ---------------------------------------------------------------------------
// opponentsByPlatform
// ---------------------------------------------------------------------------

describe('opponentsByPlatform', () => {
  it('returns an empty object for no matches', () => {
    expect(opponentsByPlatform([])).toEqual({});
  });

  it('counts platforms correctly', () => {
    const matches = [
      makeMatch({ opponentPlatform: 'Mac' }),
      makeMatch({ opponentPlatform: 'Mac' }),
      makeMatch({ opponentPlatform: 'Windows' }),
    ];
    expect(opponentsByPlatform(matches)).toEqual({ Mac: 2, Windows: 1 });
  });

  it('groups empty platform string as Unknown', () => {
    const matches = [
      makeMatch({ opponentPlatform: '' }),
      makeMatch({ opponentPlatform: 'iOS' }),
    ];
    expect(opponentsByPlatform(matches)).toEqual({ Unknown: 1, iOS: 1 });
  });

  it('handles all known platforms', () => {
    const matches = ['Mac', 'Windows', 'iOS', 'Android'].map((p) =>
      makeMatch({ opponentPlatform: p }),
    );
    expect(opponentsByPlatform(matches)).toEqual({ Mac: 1, Windows: 1, iOS: 1, Android: 1 });
  });
});
