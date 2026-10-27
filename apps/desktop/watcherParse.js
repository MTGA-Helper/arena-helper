"use strict";

// Arena Watcher log parsing (Slice 5, Oct 26, 2026) — the pure half:
// lines in, state out, no I/O. watcher.js owns the file tailing and
// feeds complete lines here; the smoke suite drives this module
// directly against fixture logs built from REAL Player.log lines, so
// what is tested is what ships.
//
// The shapes below were read off real Player.log files (Jul 9, 2026
// session, 5.5 MB; verified Oct 26, 2026), not guessed:
//   - A session "dump" line: one bare JSON object carrying
//     DeckSummaries + Decks (the deck library: DeckId -> boards of
//     {cardId, quantity}) and InventoryInfo (wildcard counts, gems,
//     gold, vault progress). This is the primary source.
//   - {"Courses": [...]} dumps: per-event course decks. Counted
//     (stats.coursesSeen) but NOT merged: the library dump in the
//     same session is the deck source of truth, and course decks are
//     event-scoped copies of it. (The repo's mtga-log-parser keeps
//     them apart the same way — deckById vs deckByEvent.)
//   - "==> EventSetDeckV3" request lines: the request field is an
//     escaped-JSON string carrying {Summary, Deck} for the deck just
//     set — merged like a one-deck dump. The "<== EventSetDeckV3(id)"
//     marker that follows carries no payload of its own; its deck
//     arrives as a bare-JSON course object and is handled (counted)
//     by the Courses rule when it has one.
//   - GRE / match payloads: out of this surge's scope (Sprint 3 owns
//     match ingestion). They carry none of the sentinels below and
//     are skipped by the prefilter.
//
// What the log does NOT contain (full recursive scan of two real
// logs, Oct 26, 2026): the owned-card collection. No Cards payload
// exists in the current client, and InventoryInfo.Changes is empty
// in every snapshot in both logs. The watcher therefore syncs the
// deck library + inventory state only; collection sync stays with
// the Slice 2 CSV upload. Nothing in this module invents the rest.
//
// Robustness rules: a line is a candidate only if it carries a
// sentinel substring (checked BEFORE any JSON.parse, so the 100 KB
// metadata blobs and match lines cost one includes()); a candidate
// that fails to parse increments stats.malformed and is dropped —
// bad lines never throw out of feedLine. State stays bounded: the
// latest deck map + inventory scalars, overwritten in place.
//
// The "../../mtga-log-parser" parsers stay where they are: that
// subsystem reads match/GRE payloads for the separate parser
// service. The deck shapes overlap, but its inputs (a finished log
// file, whole JSON objects by offset search) and mission differ;
// this module follows the same conventions it established (notably
// the "?=?" unlocalized-name skip) without coupling the two.

const SENTINELS = [
  '"InventoryInfo"',
  '"DeckSummaries"',
  '"DeckSummariesV3"',
  '"Courses"',
  '"CourseDeckSummary"',
  "EventSetDeckV3",
  "EventSetDeckV2",
];

// Log board key -> payload board key.
const BOARD_KEYS = [
  ["MainDeck", "main"],
  ["Sideboard", "sideboard"],
  ["CommandZone", "command"],
  ["Companions", "companion"],
];

function createState() {
  return {
    inventory: null, // {seqId, gems, gold, vaultProgress, wildcards:{common,uncommon,rare,mythic}}
    decks: {}, // arenaDeckId -> {deckId, name, format, cardsKnown, cards: {"grp|board": {grpId, quantity, board}}}
    stats: { lines: 0, candidates: 0, parsed: 0, malformed: 0, coursesSeen: 0, decksSeen: 0 },
  };
}

function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function isCandidate(line) {
  for (const s of SENTINELS) {
    if (line.includes(s)) return true;
  }
  return false;
}

// Player.log deck entries are {cardId, quantity}; the repo's
// deckParser also tolerates a preferredCardId fallback, so do both.
function entryGrpId(entry) {
  if (!entry || typeof entry !== "object") return 0;
  return num(entry.cardId || entry.grpId || entry.preferredCardId);
}

function applyDeckCards(state, deckId, deckObj) {
  const cards = {};
  let known = false;
  for (const [key, board] of BOARD_KEYS) {
    const entries = deckObj ? deckObj[key] : null;
    if (!Array.isArray(entries)) continue;
    known = true;
    for (const entry of entries) {
      const grpId = entryGrpId(entry);
      const quantity = num(entry && entry.quantity);
      if (!grpId || quantity <= 0) continue;
      const k = grpId + "|" + board;
      if (cards[k]) cards[k].quantity += quantity;
      else cards[k] = { grpId, quantity, board };
    }
  }
  const existing = state.decks[deckId];
  state.decks[deckId] = {
    deckId,
    name: (existing && existing.name) || "",
    format: (existing && existing.format) || null,
    cardsKnown: known,
    cards,
  };
  state.stats.decksSeen += 1;
}

function applySummary(state, summary) {
  if (!summary || typeof summary !== "object") return;
  const deckId = summary.DeckId;
  const name = typeof summary.Name === "string" ? summary.Name : "";
  // Precon decks arrive with unlocalized "?=?"-prefixed names (the
  // repo's deckParser skips them for the same reason): they are not
  // the player's decks, and the placeholder is not a name.
  if (!deckId || name.startsWith("?=?")) return;
  const deck = state.decks[deckId] || {
    deckId,
    name: "",
    format: null,
    cardsKnown: false,
    cards: {},
  };
  if (name) deck.name = name;
  const format =
    summary.Format || (summary.Attributes && summary.Attributes.Format) || null;
  if (format) deck.format = String(format);
  state.decks[deckId] = deck;
}

function applyInventory(state, inv) {
  if (!inv || typeof inv !== "object") return;
  state.inventory = {
    seqId: num(inv.SeqId),
    gems: num(inv.Gems),
    gold: num(inv.Gold),
    vaultProgress: num(inv.TotalVaultProgress),
    wildcards: {
      common: num(inv.WildCardCommons),
      uncommon: num(inv.WildCardUnCommons),
      rare: num(inv.WildCardRares),
      mythic: num(inv.WildCardMythics),
    },
  };
}

function applySessionDump(state, obj) {
  const decks = obj.Decks && typeof obj.Decks === "object" ? obj.Decks : null;
  const summaries = Array.isArray(obj.DeckSummaries)
    ? obj.DeckSummaries
    : Array.isArray(obj.DeckSummariesV3)
      ? obj.DeckSummariesV3
      : [];
  // Summaries first (names), then cards — a summary-only touch must
  // never clear cards a dump already gave the deck.
  for (const summary of summaries) applySummary(state, summary);
  if (decks) {
    for (const summary of summaries) {
      const deckId = summary && summary.DeckId;
      if (deckId && decks[deckId]) applyDeckCards(state, deckId, decks[deckId]);
    }
    // Decks with no summary still count (name unknown until one
    // arrives; buildPayload holds them back on the name check).
    for (const deckId of Object.keys(decks)) {
      if (!state.decks[deckId]) applyDeckCards(state, deckId, decks[deckId]);
    }
  }
}

function applyEventSetDeck(state, outer) {
  // The request field is itself a JSON string:
  //   {"EventName": ..., "Summary": {...}, "Deck": {...}}
  let innerStart = -1;
  let inner = null;
  if (outer && typeof outer.request === "string") {
    try {
      inner = JSON.parse(outer.request);
    } catch {
      inner = null;
    }
  }
  if (!inner) {
    // Fall back to locating the string in the raw line.
    innerStart = -1; // (raw-line recovery removed — see note below)
    return false;
  }
  if (inner.Summary) applySummary(state, inner.Summary);
  const deckId = inner.Summary && inner.Summary.DeckId;
  if (deckId && inner.Deck) applyDeckCards(state, deckId, inner.Deck);
  return true;
}

// Note on the removed fallback: an earlier draft re-scanned the raw
// line for the request JSON when the typed field was missing. Real
// lines always carry the field (verified on the Jul 9, 2026 log),
// and a heuristic second parse is exactly where malformed-line bugs
// breed — the typed path is the only path.

function applyParsedObject(state, obj) {
  if (!obj || typeof obj !== "object") return;
  if (obj.InventoryInfo) applyInventory(state, obj.InventoryInfo);

  if (obj.Decks || obj.DeckSummaries || obj.DeckSummariesV3) {
    applySessionDump(state, obj);
  }

  if (Array.isArray(obj.Courses)) {
    state.stats.coursesSeen += obj.Courses.length;
  }
  // Single-course objects (the EventSetDeck response companion, and
  // any bare {"CourseId": ...} line): a deck COPIES rides along here
  // when one is present, but courses are event scope, not library —
  // count the sighting, do not merge (see header).
  if (obj.CourseDeckSummary) {
    state.stats.coursesSeen += 1;
  }
}

// Feed ONE complete line (no trailing newline). Returns true when
// the line changed syncable state (inventory or decks). Never throws.
function feedLine(state, line) {
  state.stats.lines += 1;
  if (typeof line !== "string" || line.length === 0) return false;
  if (!isCandidate(line)) return false;
  state.stats.candidates += 1;

  const before = state.inventory;
  const decksBefore = state.stats.decksSeen;

  const trimmed = line.trim();
  if (trimmed.startsWith("{")) {
    let obj;
    try {
      obj = JSON.parse(trimmed);
    } catch {
      state.stats.malformed += 1;
      return false;
    }
    state.stats.parsed += 1;
    applyParsedObject(state, obj);
  } else if (trimmed.includes("==> EventSetDeck")) {
    // Prefixed variant: "[UnityCrossThreadLogger]==> EventSetDeckV3 {...}"
    const brace = trimmed.indexOf("{");
    if (brace < 0) {
      // The "<== EventSetDeckV3(id)" response marker also matches
      // the sentinel and carries no payload — a normal line, not a
      // malformed one.
      return false;
    }
    let obj;
    try {
      obj = JSON.parse(trimmed.slice(brace));
    } catch {
      state.stats.malformed += 1;
      return false;
    }
    state.stats.parsed += 1;
    if (!applyEventSetDeck(state, obj)) state.stats.malformed += 1;
  } else {
    // A sentinel appeared on a line with no JSON payload (the
    // "<== EventSetDeckV3(id)" marker): nothing to apply.
    return false;
  }

  return state.inventory !== before || state.stats.decksSeen !== decksBefore;
}

// The POST /watcher/sync payload: decks that have both a name and a
// known card list, plus the latest inventory snapshot. Decks known
// only by summary (no cards seen yet) are held back — syncing an
// empty card list would REPLACE the stored deck with nothing under
// the endpoint's per-deck replacement rule.
function buildPayload(state) {
  const decks = [];
  for (const deck of Object.values(state.decks)) {
    if (!deck.cardsKnown || !deck.name) continue;
    decks.push({
      deck_id: deck.deckId,
      name: deck.name,
      format: deck.format || undefined,
      cards: Object.values(deck.cards).map((c) => ({
        grp_id: c.grpId,
        quantity: c.quantity,
        board: c.board,
      })),
    });
  }
  decks.sort((a, b) => a.name.localeCompare(b.name));
  const payload = { decks };
  if (state.inventory) {
    payload.inventory = {
      wildcards: state.inventory.wildcards,
      gems: state.inventory.gems,
      gold: state.inventory.gold,
      vault_progress: state.inventory.vaultProgress,
    };
  }
  return payload;
}

module.exports = { createState, feedLine, buildPayload, isCandidate, SENTINELS };
