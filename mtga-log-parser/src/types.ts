// === Match result primitives ===
export type GameResult = 1 | 0 | 'Draw' | null;
export type MatchResult = 'Win' | 'Loss' | 'Draw' | null;
export type MatchFilter = (eventId: string) => boolean;

// === Public data shapes ===

export interface Match {
  id: string;           // matchId UUID from log
  timestamp: number;    // ms epoch from log
  myPlayerId: string;   // local player's userId from reservedPlayers
  opponentPlayerId: string; // opponent's userId from reservedPlayers
  myGamerTag: string;   // local player's playerName from reservedPlayers
  opponentGamerTag: string; // opponent's playerName from reservedPlayers
  opponent: string;     // opponent playerName from log
  opponentPlatform: string; // opponent's client platform from log, e.g. "Mac", "Windows", "iOS", "Android"
  opponentDeck: string;   // manual entry, default ''
  opponentColors: string; // manual entry, e.g. "WU", "BR", "RG" — standard MTG color letters
  myDeck: string;         // auto-detected from log, default ''
  onPlay: boolean | null; // auto-detected from log
  game1: GameResult;
  game2: GameResult;
  game3: GameResult;
  matchResult: MatchResult; // calculated, not stored raw
  eventId: string;      // e.g. "Ranked"
  importedAt: number;   // when we parsed this match
  notes: string;       // manual entry, default ''
}

export type MatchUpdate = Partial<Pick<Match, 'opponentDeck' | 'opponentColors' | 'myDeck' | 'notes'>>;

export interface GameSnapshot {
  matchId: string;
  gameNumber: 1 | 2 | 3;
  myMulliganCount: number;       // 0 = kept 7; absent in log when 0, so defaults to 0
  opponentMulliganCount: number;
  myFinalLife: number;           // life total at GameStage_GameOver
  opponentFinalLife: number;
  turnCount: number;             // max(myTurnNumber, oppTurnNumber) at game end
  gameEndReason: 'life' | 'concede' | 'timeout' | 'draw' | 'unknown';
  openingHandGrpIds?: number[];  // grpIds from initial 7-card hand before any mulligan decision
}

export interface BoardCard {
  instanceId: number;
  grpId: number;
  name: string;           // resolved from card DB
  power?: number;
  toughness?: number;
  isTapped: boolean;
  counters?: Record<string, number>;
}

export interface TurnSnapshot {
  matchId: string;
  gameNumber: 1 | 2 | 3;
  turnNumber: number;
  activePlayerIsMe: boolean;
  phase: string;
  myLife: number;
  oppLife: number;
  myHand: BoardCard[];
  oppHandCount: number;
  myBattlefield: BoardCard[];
  oppBattlefield: BoardCard[];
  myGraveyard: BoardCard[];
  oppGraveyard: BoardCard[];
  myExile: BoardCard[];
  oppExile: BoardCard[];
  stack: BoardCard[];
}

/** One record per turn, listing the grpIds drawn by the local player that turn. */
export interface TurnDrawRecord {
  matchId: string;
  gameNumber: number;
  turnNumber: number;
  /** grpIds drawn by the local player this turn (in draw order). */
  drawnGrpIds: number[];
}

/** One record per in-game action (spell cast, ability activated/triggered). */
export interface GameAction {
  matchId: string;
  gameNumber: number;
  turnNumber: number;
  /** Category of the action as reported by MTGA. */
  type: 'CastSpell' | 'ActivateAbility' | 'TriggerAbility';
  /** True if the local player performed this action. */
  castByMe: boolean;
  /** grpId of the source card/permanent. */
  sourceGrpId: number;
  /** instanceId of the source card/permanent. */
  sourceInstanceId: number;
  /** instanceIds of targets (empty if no targets or targets unresolvable). */
  targetInstanceIds: number[];
  /** grpIds of targets, resolved from game state at time of action (empty if hidden). */
  targetGrpIds: number[];
}

// === Deck types ===

export interface CardEntry {
  cardId: number;
  quantity: number;
}

export interface DeckList {
  main: CardEntry[];
  sideboard: CardEntry[];
}

// === Parse stats ===

export interface ParseStats {
  filesScanned: number;
  linesScanned: number;
  candidateLines: { deck: number; matchState: number; gre: number };
  parseErrors:   { deck: number; matchState: number; gre: number };
  matchesStarted: number;
  matchesCompleted: number;
  droppedActions: { unresolvableGrpId: number; orphanTarget: number };
}

// === Parse API types ===

export interface ParseConfig {
  /** Path to Player.log or a directory containing Player.log/UTC_Log files */
  logDir: string;
  /**
   * Filter which matches to include. Receives the raw MTGA eventId string
   * from reservedPlayers[].eventId. Called once per player; a match is
   * included only if ALL players pass the filter.
   *
   * Defaults to () => true (all matches).
   * Use MatchFilters helpers for common presets.
   */
  matchFilter?: MatchFilter;
  /**
   * Optional callback to resolve opponent colors from card grpIds.
   * If omitted, match.opponentColors will be an empty string.
   *
   * Typical implementation queries the MTGA SQLite card database.
   * Mac:     ~/Library/Application Support/com.wizards.mtga/Downloads/Raw/Raw_CardDatabase_*.mtga
   * Windows: %APPDATA%\..\LocalLow\Wizards Of The Coast\MTGA\Downloads\Raw\Raw_CardDatabase_*.mtga
   */
  resolveColors?: (grpIds: number[]) => Promise<string>;
}

export interface ParseResult {
  matches: Match[];
  opponentGrpIds: Map<string, Set<number>>;
  gameSnapshots: GameSnapshot[];
  boardSnapshots: TurnSnapshot[];
  /** Per-turn records of grpIds drawn by the local player. Only turns where at least one draw was tracked are included. */
  turnDrawRecords: TurnDrawRecord[];
  /** All game actions (spells cast, abilities used) where the source grpId was resolvable. */
  gameActions: GameAction[];
  myDeckListMap: Map<string, DeckList>;
  deckUsages: Map<string, { deck: DeckList; timestamp: number }>;
  /** Returns raw accumulated zone/object state for a match+game — useful for diagnosing unexpected board snapshots. */
  debugBoardState: (matchId: string, gameNumber: number) => RawStateDebug | null;
  /** Aggregate counters from the parse run. */
  stats: ParseStats;
}

export interface ProcessAnnotationsArgs {
  gsm: Record<string, unknown>;
  state: LiveGameState;
  currentMatchId: string;
  gameNumber: number;
  drawsByTurnKey: Map<string, TurnDrawRecord>;
  stats: ParseStats;
}

// === Collector interfaces ===

export interface GameDataCollector {
  // Call this for every parsed GRE greToClientEvent object that contains GameStateMessages
  collect(
    obj: Record<string, unknown>,
    currentMatchId: string | null,
    localTeamIdMap: Map<string, number>,
  ): void;
  snapshots(): GameSnapshot[];
}

export interface RawStateDebug {
  gameNumber: number | null;
  localSeatId: number | null;
  turnInfo: RawTurnInfo | null;
  zones: Array<{ zoneId: number; type?: string; ownerSeatId?: number; objectCount: number }>;
  gameObjects: Array<{ instanceId: number; grpId?: number; zoneId?: number; type?: string; ownerSeatId?: number; controllerSeatId?: number; isTapped: boolean }>;
}

export interface BoardStateCollector {
  collect(
    obj: Record<string, unknown>,
    currentMatchId: string | null,
    stats?: ParseStats,
  ): void;
  snapshots(): TurnSnapshot[];
  drawRecords(): TurnDrawRecord[];
  actionRecords(): GameAction[];
  rawState(matchId: string, gameNumber: number): RawStateDebug | null;
}

// === Internal raw GRE object types ===

export interface RawGameObject {
  instanceId: number;
  grpId?: number;
  ownerSeatId?: number;
  controllerSeatId?: number;
  type?: string;
  power?: number;
  toughness?: number;
  zoneId?: number;
  isTapped?: boolean;
  counters?: Record<string, number>;
}

export interface RawZone {
  zoneId: number;
  type?: string;
  ownerSeatId?: number;
  objectInstanceIds?: number[];
}

export interface RawPlayer {
  systemSeatNumber?: number;
  lifeTotal?: number;
  turnNumber?: number;
}

export interface RawTurnInfo {
  turnNumber?: number;
  activePlayer?: number;
  phase?: string;
  step?: string;
}

export interface LiveGameState {
  gameObjects: Map<number, RawGameObject>;
  zones: Map<number, RawZone>;
  players: Map<number, RawPlayer>;
  turnInfo: RawTurnInfo | null;
  gameNumber: number | null;
  localSeatId: number | null;
  // MTGA sometimes advances turnNumber before all combat phases are logged.
  // Track the turn and active player at BeginCombat so continuation phases
  // (DeclareAttackers → CombatDamage → EndCombat) are attributed to the correct turn.
  activeCombatTurn: number | null;
  activeCombatPlayer: number | undefined;
}

// === Internal collector state ===

// Per-game mutable state accumulated before we see GameStage_GameOver
export interface SnapshotBuilder {
  myMulligan: number;
  oppMulligan: number;
  // Last life totals seen in any non-GameOver message, used as fallback when
  // GameStage_GameOver omits lifeTotal (common on life-total deaths).
  lastMyLife: number | null;
  lastOppLife: number | null;
  openingHandCaptured: boolean;
  openingHandGrpIds: number[];
}

export interface CollectorState {
  liveStates: Map<string, LiveGameState>;
  lastTurnNumbers: Map<string, number>;
  lastPhases: Map<string, string>;
  lastEmittedLabel: Map<string, string>;
  currentGameNumbers: Map<string, number>;
  completed: TurnSnapshot[];
  drawsByTurnKey: Map<string, TurnDrawRecord>;
  actionsByGameKey: Map<string, GameAction[]>;
}

// === Internal session state ===

export interface Session {
  localPlayerId: string | null;
  matchMap: Map<string, Match>;
  localTeamIdMap: Map<string, number>;
  opponentGrpIds: Map<string, Set<number>>;
  myDeckListMap: Map<string, DeckList>;
  pendingDeckName: string;
  pendingDeckList: DeckList;
  currentMatchId: string | null;
  deckByEvent: Map<string, { name: string; deck: DeckList }>;
  gameEndReasonsMap: Map<string, string[]>;
  deckUsages: Map<string, { deck: DeckList; timestamp: number }>;
  seatToTeamByMatch: Map<string, Map<number, number>>;
  localTeamIdGREConfirmed: Set<string>;
}

export interface RawGameResult {
  winningTeamId: number;
  reason: string;
}

export interface ParseSession {
  session: Session;
  gameDataCollector: GameDataCollector;
  boardStateCollector: BoardStateCollector;
  matchFilter: MatchFilter;
  stats: ParseStats;
}
