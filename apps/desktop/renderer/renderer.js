// Arena Helper renderer (Slice 1): engine status, sign-in/register, and a
// signed-in home that proves the engine connection with the live deck list.
// All calls go through the preload bridge; this file holds no URLs and no
// token.
//
// Slice 2: the Collection section — engine stats, the list-vs-stats
// reconciliation line (computed by collectionLogic.js, the same module
// the smoke test exercises), a name filter, and CSV upload/refresh.

const $ = (id) => document.getElementById(id);
const LIST_CAP = 500; // render cap; the full list stays in memory for filtering

let collectionList = [];
let collectionStats = null;

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
  $("auth-view").classList.remove("hidden");
});

refreshEngineStatus();
