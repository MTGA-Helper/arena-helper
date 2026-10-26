// Arena Helper — collection reconciliation logic (Slice 2, Oct 26, 2026).
//
// Pure functions, no DOM and no network: the renderer uses them to show
// whether the collection list and the engine's /collection/stats agree,
// and the smoke test (test/api-smoke.js) exercises the exact same code
// against the live payloads, so what the app displays is what is tested.
//
// Loaded two ways: as a plain <script> in the renderer (window
// .collectionLogic) and via require() from the Node smoke test.
(function (exports) {
  "use strict";

  // summarizeCollection(list, stats) -> {
  //   rowCount,        // rows in the list payload
  //   qtySum,          // sum of quantity over the list
  //   rowsAgree,       // rowCount === stats.unique_cards
  //   totalsAgree,     // qtySum === stats.total_cards
  //   allAgree,        // both
  // }
  // stats fields are the engine's own names (total_cards, unique_cards).
  function summarizeCollection(list, stats) {
    const rows = Array.isArray(list) ? list : [];
    const qtySum = rows.reduce((acc, item) => acc + (item.quantity || 0), 0);
    const rowsAgree = Boolean(stats) && rows.length === stats.unique_cards;
    const totalsAgree = Boolean(stats) && qtySum === stats.total_cards;
    return {
      rowCount: rows.length,
      qtySum,
      rowsAgree,
      totalsAgree,
      allAgree: rowsAgree && totalsAgree,
    };
  }

  // Case-insensitive name filter for the collection list. An empty query
  // returns the list unchanged.
  function filterCollection(list, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return list;
    // FIX (hub #351): guard the list the same way summarizeCollection does
    // above (a non-array payload crashed here), and tolerate nameless
    // engine rows -- the old predicate threw on item.name mid-search and
    // broke list rendering.
    if (!Array.isArray(list)) return [];
    return list.filter((item) => String((item && item.name) || "").toLowerCase().includes(q));
  }

  exports.summarizeCollection = summarizeCollection;
  exports.filterCollection = filterCollection;
})(typeof module !== "undefined" && module.exports ? module.exports : (window.collectionLogic = {}));
