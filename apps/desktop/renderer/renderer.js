// Arena Helper renderer (Slice 1): engine status, sign-in/register, and a
// signed-in home that proves the engine connection with the live deck list.
// All calls go through the preload bridge; this file holds no URLs and no
// token.
//
// Slice 4: the Recommendations section — the engine's next-action
// answer rendered through recommendationsLogic (with the canned
// fallback labeled as a fallback, never dressed up as advice), and
// deck choosing in the deck detail: the full four-rarity wildcard
// bill and a per-card Craft column priced at the cheapest printing.
//
// Slice 3: the Decks section — the engine's ranked deck list with
// its completion math checked in the open (decksLogic.deckMath),
// and a per-deck detail: full card list with type lines/subtypes,
// per-card owned/missing, and the stored engine analysis as served.
//
// Slice 2: the Collection section — engine stats, the list-vs-stats
// reconciliation line (computed by collectionLogic.js, the same module
// the smoke test exercises), a name filter, and CSV upload/refresh.

const $ = (id) => document.getElementById(id);
const LIST_CAP = 500; // render cap; the full list stays in memory for filtering

let collectionList = [];
let collectionStats = null;
let decksList = [];

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function refreshEngineStatus() {
  const el = $("engine-status");
  const res = await window.arena.action("engine-health");
  if (res.ok) {
    el.innerHTML = 'Engine: <span class="ok">healthy</span> · database ' +
      res.data.database + " · " + res.data.engines_loaded + " engines loaded";
  } else {
    el.innerHTML = 'Engine: <span class="bad">unreachable</span> — ' + escapeHtml(res.error);
  }
}

async function showHome() {
  const session = await window.arena.action("session");
  if (!session.ok || !session.data.signedIn) return;
  $("auth-view").classList.add("hidden");
  $("home-view").classList.remove("hidden");
  $("collection-view").classList.remove("hidden");
  $("decks-view").classList.remove("hidden");
  $("recommendations-view").classList.remove("hidden");
  $("welcome").textContent = "Signed in as " + session.data.email;
  const res = await window.arena.action("decks");
  if (res.ok) {
    $("decks-summary").textContent =
      "The engine is tracking " + res.data.length + " recommended decks for your collection:";
    $("decks-list").innerHTML = res.data
      .slice(0, 5)
      .map((d) => "<li>" + escapeHtml(d.deck_name) + " — " + d.completion_percent + "% complete</li>")
      .join("");
  } else {
    $("decks-summary").textContent = "Could not load decks: " + res.error;
  }
  loadCollection();
  loadDecks();
  loadNextAction();
}

// --- Collection (Slice 2) ---------------------------------------------

function renderCollection() {
  if (!collectionStats) return;
  $("stat-total").textContent = collectionStats.total_cards;
  $("stat-unique").textContent = collectionStats.unique_cards;
  $("stat-rares").textContent = collectionStats.rares;
  $("stat-mythics").textContent = collectionStats.mythics;
  const wc = collectionStats.wildcards || {};
  $("stat-wildcards").textContent = (wc.rare || 0) + " / " + (wc.mythic || 0);

  const s = window.collectionLogic.summarizeCollection(collectionList, collectionStats);
  const el = $("collection-reconcile");
  if (s.allAgree) {
    el.innerHTML = "List and engine stats agree: <span class=\"agree\">" +
      s.rowCount + " unique cards · " + s.qtySum + " total copies</span>";
  } else {
    el.innerHTML = "<span class=\"disagree\">List and engine stats disagree</span> — list shows " +
      s.rowCount + " rows / " + s.qtySum + " copies; stats say " +
      collectionStats.unique_cards + " unique / " + collectionStats.total_cards + " total.";
  }
  renderCollectionList();
}

function renderCollectionList() {
  const filtered = window.collectionLogic.filterCollection(collectionList, $("collection-search").value);
  const shown = filtered.slice(0, LIST_CAP);
  $("collection-showing").textContent = "Showing " + shown.length + " of " + filtered.length +
    " cards" + (filtered.length !== collectionList.length ? " (filtered from " + collectionList.length + ")" : "");
  const wrap = $("collection-list");
  wrap.textContent = "";
  const table = document.createElement("table");
  const head = document.createElement("tr");
  for (const label of ["Card", "Types", "Qty"]) {
    const th = document.createElement("th");
    th.textContent = label;
    if (label === "Qty") th.className = "qty";
    head.appendChild(th);
  }
  table.appendChild(head);
  for (const item of shown) {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = item.name;
    const types = document.createElement("td");
    types.textContent = (item.types || []).join(", ");
    const qty = document.createElement("td");
    qty.className = "qty";
    qty.textContent = item.quantity;
    tr.append(name, types, qty);
    table.appendChild(tr);
  }
  wrap.appendChild(table);
}

async function loadCollection() {
  $("collection-error").textContent = "";
  const res = await window.arena.action("collection");
  if (res.ok) {
    collectionList = res.data.list;
    collectionStats = res.data.stats;
    renderCollection();
  } else {
    $("collection-reconcile").textContent = "Could not load the collection.";
    $("collection-error").textContent = res.error;
  }
}

$("collection-search").addEventListener("input", renderCollectionList);
$("collection-refresh-btn").addEventListener("click", loadCollection);
$("collection-upload-btn").addEventListener("click", async () => {
  $("collection-error").textContent = "";
  $("collection-upload-result").textContent = "";
  const res = await window.arena.action("collection-upload");
  if (!res.ok) {
    $("collection-error").textContent = res.error;
    return;
  }
  if (res.data.canceled) {
    $("collection-upload-result").textContent = "Upload canceled — collection unchanged.";
    return;
  }
  const s = res.data.summary;
  $("collection-upload-result").textContent =
    "Imported " + s.cards_imported + " cards (" + s.unique_cards + " unique) · matched " +
    s.matched_cards + " rows · unmatched " + s.unmatched_cards + " · duplicate rows merged: " + s.duplicates;
  collectionList = res.data.list;
  collectionStats = res.data.stats;
  renderCollection();
});

// --- Decks (Slice 3) ----------------------------------------------------

function renderDecks() {
  const wrap = $("decks-table-wrap");
  wrap.textContent = "";
  const badMath = decksList.filter((d) => !window.decksLogic.deckMath(d).agrees);
  $("decks-summary-line").textContent =
    decksList.length + " decks from the engine, in the engine's rank order." +
    (badMath.length
      ? " Warning: " + badMath.length + " deck(s) have completion numbers that do not tie out."
      : " Every deck's owned + missing ties out to its card total.") +
    " Click a deck for its cards and analysis.";
  const table = document.createElement("table");
  const head = document.createElement("tr");
  for (const label of ["Deck", "Archetype", "Format", "Tier", "Complete", "Owned", "Wildcards", "Score"]) {
    const th = document.createElement("th");
    th.textContent = label;
    if (["Tier", "Complete", "Owned", "Wildcards", "Score"].includes(label)) th.className = "num";
    head.appendChild(th);
  }
  table.appendChild(head);
  for (const d of decksList) {
    const tr = document.createElement("tr");
    tr.className = "deck-row";
    // Slice 4: the Wildcards column is the full four-rarity bill's
    // total (recommendationsLogic), with the itemized bill as the
    // cell's title — the pre-Slice-4 cell showed only rare/mythic,
    // which understated every deck with uncommon/common gaps.
    const bill = window.recommendationsLogic.wildcardBill(d.wildcard_cost);
    const cells = [
      d.deck_name,
      d.archetype || "—",
      d.format || "—",
      d.tier == null ? "—" : String(d.tier),
      d.completion_percent + "%",
      (d.cards_owned || 0) + " / " + (d.cards_required || 0),
      String(bill.total),
      d.rank_score == null ? "—" : d.rank_score.toFixed(1),
    ];
    cells.forEach((text, i) => {
      const td = document.createElement("td");
      td.textContent = text;
      if (i >= 3) td.className = "num";
      if (i === 6) td.title = window.recommendationsLogic.billText(d.wildcard_cost);
      tr.appendChild(td);
    });
    if (d.deck_id != null) {
      tr.addEventListener("click", () => loadDeckDetail(d.deck_id));
    } else {
      tr.title = "Deck detail needs the Slice 3 engine (this engine does not return deck ids yet).";
    }
    table.appendChild(tr);
  }
  wrap.appendChild(table);
}

async function loadDecks() {
  $("decks-error").textContent = "";
  const res = await window.arena.action("decks");
  if (res.ok) {
    decksList = res.data;
    renderDecks();
  } else {
    $("decks-summary-line").textContent = "Could not load decks.";
    $("decks-error").textContent = res.error;
  }
}

function renderDeckDetail(detail) {
  const s = window.decksLogic.summarizeDeckDetail(detail);
  $("deck-detail").classList.remove("hidden");
  $("deck-detail-title").textContent = detail.deck_name;
  $("deck-detail-meta").textContent =
    (detail.archetype || "—") + " · " + (detail.format || "—") +
    " · Tier " + (detail.tier == null ? "—" : detail.tier) +
    " · Winrate " + detail.winrate + "%" +
    " · " + detail.completion_percent + "% complete (" + detail.cards_owned + " / " + detail.cards_required + ")" +
    " · Wildcards to finish: " + window.recommendationsLogic.billText(detail.wildcard_cost) +
    " · " + s.totalCards + " cards, " + s.cardKinds + " distinct, " + s.missingKinds + " short";

  const analysisEl = $("deck-analysis");
  analysisEl.textContent = "";
  if (s.hasAnalysis) {
    const a = detail.analysis;
    const grid = document.createElement("div");
    grid.className = "stats-grid";
    for (const [label, value] of [
      ["Final score", a.final_score],
      ["Synergy", a.synergy_score],
      ["Consistency", a.consistency_score],
      ["Mana", a.mana_score],
      ["Meta", a.meta_score],
    ]) {
      const cell = document.createElement("div");
      const span = document.createElement("span");
      span.textContent = value;
      const small = document.createElement("small");
      small.textContent = label;
      cell.append(span, small);
      grid.appendChild(cell);
    }
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = "Analysis as computed and stored by the engine's deck analysis — shown exactly as served.";
    analysisEl.append(grid, note);
  } else {
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = "No stored analysis for this deck yet — it appears once the engine's deck analysis has run on it.";
    analysisEl.appendChild(note);
  }

  const wrap = $("deck-cards-wrap");
  wrap.textContent = "";
  const table = document.createElement("table");
  const head = document.createElement("tr");
  for (const label of ["Qty", "Card", "Type", "Rarity", "Craft", "Own", "Missing"]) {
    const th = document.createElement("th");
    th.textContent = label;
    if (["Qty", "Own", "Missing"].includes(label)) th.className = "num";
    head.appendChild(th);
  }
  table.appendChild(head);
  for (const c of detail.cards || []) {
    const tr = document.createElement("tr");
    const values = [
      String(c.quantity),
      c.name,
      c.type_line || (c.types || []).join(" "),
      c.rarity,
      // Slice 4: the Craft column prices the missing copies at the
      // cheapest printing (the engine's craft_rarity); basics are
      // free on Arena and say so.
      c.basic ? "free" : (c.craft_rarity || c.rarity),
      String(c.owned || 0),
      String(c.missing || 0),
    ];
    values.forEach((text, i) => {
      const td = document.createElement("td");
      td.textContent = text;
      if ([0, 5, 6].includes(i)) td.className = "num";
      if (i === 6 && (c.missing || 0) > 0) td.classList.add("missing");
      tr.appendChild(td);
    });
    table.appendChild(tr);
  }
  wrap.appendChild(table);
}

async function loadDeckDetail(deckId) {
  $("decks-error").textContent = "";
  const res = await window.arena.action("deck-detail", { deckId });
  if (res.ok) {
    renderDeckDetail(res.data);
  } else {
    $("decks-error").textContent = res.error;
  }
}

$("decks-refresh-btn").addEventListener("click", loadDecks);

// --- Recommendations (Slice 4) ------------------------------------------

function renderNextAction(payload) {
  const v = window.recommendationsLogic.nextActionView(payload);
  const line = $("next-action-line");
  const reasons = $("next-action-reasons");
  const note = $("next-action-note");
  reasons.textContent = "";
  if (!v.available) {
    line.textContent = "The engine has no next action for this collection right now.";
    note.textContent = "";
    return;
  }
  line.textContent = "Craft " + v.cost + " × " + v.cardName +
    " (" + v.rarity + ") — next step toward " + v.deckName + ".";
  for (const r of v.reasons) {
    const li = document.createElement("li");
    li.textContent = r;
    reasons.appendChild(li);
  }
  note.textContent = v.isFallback
    ? "This is the engine's safety default, not a computed recommendation — it appears when the engine cannot see your decks' missing cards."
    : "Computed by the engine from your collection and its ranked decks" +
      (v.confidence ? " · engine confidence: " + v.confidence : "") + ".";
}

async function loadNextAction() {
  $("recommendations-error").textContent = "";
  const res = await window.arena.action("next-action");
  if (res.ok) {
    renderNextAction(res.data);
  } else {
    $("next-action-line").textContent = "Could not load the recommendation.";
    $("recommendations-error").textContent = res.error;
  }
}

$("next-action-refresh-btn").addEventListener("click", loadNextAction);

// --- Auth (Slice 1) -----------------------------------------------------

$("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("auth-error").textContent = "";
  const pw = $("password").value;
  const res = await window.arena.action("login", {
    email: $("email").value.trim(),
    pw,
  });
  if (res.ok) showHome();
  else $("auth-error").textContent = res.error;
});

$("register-btn").addEventListener("click", async () => {
  $("auth-error").textContent = "";
  const pw = $("password").value;
  const res = await window.arena.action("register", {
    email: $("email").value.trim(),
    pw,
  });
  if (res.ok) {
    $("auth-error").textContent = "Account created — now sign in.";
  } else {
    $("auth-error").textContent = res.error;
  }
});

$("logout-btn").addEventListener("click", async () => {
  await window.arena.action("logout");
  $("home-view").classList.add("hidden");
  $("collection-view").classList.add("hidden");
  $("decks-view").classList.add("hidden");
  $("recommendations-view").classList.add("hidden");
  $("auth-view").classList.remove("hidden");
});

refreshEngineStatus();
