// Arena Helper — recommendations + deck-choosing logic (Slice 4,
// Oct 26, 2026).
//
// Pure functions, no DOM and no network: the renderer uses them to
// lay out the Recommendations section and the deck-choosing wildcard
// bill, and the smoke test (test/api-smoke.js) exercises the exact
// same code against the engine payloads, so what the app displays
// is what is tested.
//
// Loaded two ways: as a plain <script> in the renderer (window
// .recommendationsLogic) and via require() from the Node smoke test.
(function (exports) {
  "use strict";

  const BUCKETS = ["common", "uncommon", "rare", "mythic"];

  // wildcardBill(wc) -> { common, uncommon, rare, mythic, total }
  // Normalizes the engine's wildcard_cost: any subset of the four
  // buckets (older engine builds serve only rare/mythic) becomes a
  // full bill with a total. Non-numeric values count as 0.
  function wildcardBill(wc) {
    const src = wc || {};
    const bill = { common: 0, uncommon: 0, rare: 0, mythic: 0, total: 0 };
    for (const b of BUCKETS) {
      const n = Number(src[b]);
      bill[b] = Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
      bill.total += bill[b];
    }
    return bill;
  }

  // billText(wc) -> the deck-choosing bill in one line, e.g.
  // "41 wildcards — 10 mythic · 25 rare · 5 uncommon · 1 common".
  // Buckets at zero are omitted; a fully owned deck reads plainly.
  function billText(wc) {
    const bill = wildcardBill(wc);
    if (bill.total === 0) return "0 wildcards — fully owned";
    const parts = [];
    for (const b of ["mythic", "rare", "uncommon", "common"]) {
      if (bill[b] > 0) parts.push(bill[b] + " " + b);
    }
    return bill.total + (bill.total === 1 ? " wildcard" : " wildcards") +
      " — " + parts.join(" · ");
  }

  // nextActionView(payload) -> {
  //   available,   // the engine returned an answer at all
  //   isFallback,  // the answer is the engine's safety default,
  //                // not a computed recommendation
  //   cardName, rarity, cost, deckName, confidence, reasons[]
  // }
  // The engine's next-action service falls back to a canned
  // candidate (its deck name carries "(Fallback)") whenever the
  // live candidate fetch fails; the app must label that honestly
  // instead of dressing it up as advice.
  function nextActionView(payload) {
    if (!payload || typeof payload !== "object") {
      return { available: false, isFallback: false, cardName: null,
               rarity: null, cost: 0, deckName: null, confidence: null,
               reasons: [] };
    }
    // The service's answer carries the deck it serves only inside
    // impact.unlocks — there is no top-level deck_name field.
    const unlocks = payload.impact && Array.isArray(payload.impact.unlocks)
      ? payload.impact.unlocks : [];
    const deckName = unlocks[0] || null;
    return {
      available: Boolean(payload.card_name),
      isFallback: Boolean(deckName && String(deckName).includes("(Fallback)")),
      cardName: payload.card_name || null,
      rarity: payload.rarity || null,
      cost: payload.cost || 0,
      deckName: deckName,
      confidence: payload.confidence || null,
      reasons: Array.isArray(payload.reason) ? payload.reason : [],
    };
  }

  exports.wildcardBill = wildcardBill;
  exports.billText = billText;
  exports.nextActionView = nextActionView;
})(typeof module !== "undefined" && module.exports ? module.exports : (window.recommendationsLogic = {}));
