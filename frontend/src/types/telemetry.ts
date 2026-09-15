export interface TurnDrawRecord {
  cardName: string;
  cardId?: string;
  drawIndex: number;
}

export interface GameAction {
  actionType: string;
  playerId?: string;
  cardId?: string;
  payload: Record<string, unknown>;
}

export interface TurnSnapshot {
  turnNumber: number;
  activePlayer?: string;
  draws: TurnDrawRecord[];
  actions: GameAction[];
  rawData?: Record<string, unknown>;
}

export interface GameSnapshot {
  gameNumber: number;
  playerLife?: number;
  opponentLife?: number;
  activePlayer?: string;
  turns: TurnSnapshot[];
  rawData?: Record<string, unknown>;
}

export interface Match {
  matchId: string;
  playerId?: string;
  opponentId?: string;
  startedAt?: string;
  endedAt?: string;
  result?: string;
  games: GameSnapshot[];
  metadata?: Record<string, unknown>;
}

export interface MatchTelemetryV1 {
  match_id: string;
  timestamp: string;
  my_deck: Record<string, unknown> | unknown[];
  opponent_deck: Record<string, unknown> | unknown[];
  opponent_colors: unknown[];
  match_result: string;
  event_id: string;
  on_play: boolean;
  opponent_platform: string;
}

export interface MatchIngestResponse extends MatchTelemetryV1 {
  id: number;
  raw_payload: Record<string, unknown>;
}

export interface CardEntry {
  cardId: string;
  cardName: string;
  quantity: number;
}

export interface DeckList {
  deckId: string;
  name?: string;
  format?: string;
  cards: CardEntry[];
}

export interface ParseResult {
  matches: Match[];
  decks: DeckList[];
  errors?: string[];
}
