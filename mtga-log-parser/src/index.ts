// Main entry point — re-exports all public API surface

// Core parse functions
export { parseAllLogs, parseAllLogsWithDebug, MatchFilters } from './logParser.js';

// Sub-collector factories
export { createGameDataCollector } from './gameDataParser.js';
export { createBoardStateCollector } from './boardStateParser.js';

// All types from the single types file
export type {
  // Match result primitives
  GameResult,
  MatchResult,
  MatchUpdate,
  // Public data shapes
  Match,
  GameSnapshot,
  BoardCard,
  TurnSnapshot,
  TurnDrawRecord,
  GameAction,
  // Deck types
  CardEntry,
  DeckList,
  // Parse API types
  ParseConfig,
  ParseResult,
  ParseStats,
  // Collector interfaces
  GameDataCollector,
  BoardStateCollector,
  RawStateDebug,
} from './types.js';

// Analytics
export { opponentsByPlatform } from './analytics.js';
