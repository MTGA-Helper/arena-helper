// Arena Helper — deck parity + detail logic (Slice 3, Oct 26, 2026).
//
// Pure functions, no DOM and no network: the renderer uses them to lay
// out the decks view, and the smoke test (test/api-smoke.js) exercises
// the exact same code against the live payloads, so what the app
// displays is what is tested.
//
// Loaded two ways: as a plain <script> in the renderer (window
// .decksLogic) and via require() from the Node smoke test.
(function (exports) {
  "use strict";

  // parityReport(decks, expectedNames) -> {
  //   count,          // decks the engine returned
  //   missingNames,   // expected names the engine did not return
  //   extraNames,     // names returned that were not expected
  //   complete,       // exact set match
  // }
  // The smoke test feeds it the Phase 0 gate's 14 deck names; the
  // renderer feeds it the list's own names (a structural self-check).
  function parityReport(decks, expectedNames) {
    const list = Array.isArray(decks) ? decks : [];
    const names = list.map((d) => d.deck_name);
    const expected = Array.isArray(expectedNames) ? expectedNames : [];
    const missingNames = expected.filter((n) => !names.includes(n));
    const extraNames = names.filter((n) => !expected.includes(n));
    return {
      count: list.length,
      missingNames,
      extraNames,
      complete: missingNames.length === 0 && extraNames.length === 0,
    };
  }

  // deckMath(deck) -> { required, owned, missingTotal, agrees }
  // The list payload's own invariant: cards_owned + the total deficit
  // across missing_cards must equal cards_required. If this ever
  // disagrees, the engine's numbers do not tie out and the app should
  // say so rather than render them blind.
  function deckMath(deck) {
    const missing = Array.isArray(deck.missing_cards) ? deck.missing_cards : [];
    const missingTotal = missing.reduce((acc, c) => acc + (c.quantity || 0), 0);
    const required = deck.cards_required || 0;
    const owned = deck.cards_owned || 0;
    // FIX (Oct 26, 2026; hub #327 F1): "agrees" is only a real check
    // when the payload actually carries the numbers being tied out.
    // Before, a deck whose payload lacked cards_required /
    // cards_owned / missing_cards defaulted them to 0 / 0 / [] and
    // could "agree" vacuously (0 + 0 === 0), so the decks summary
    // claimed a tie-out the engine never made. Absent fields now
    // report agrees: false; the arithmetic itself is unchanged.
    // (Pre-fix: agrees: owned + missingTotal === required, computed
    // unconditionally.)
    const agrees =
      deck.cards_required != null &&
      deck.cards_owned != null &&
      Array.isArray(deck.missing_cards) &&
      owned + missingTotal === required;
    return { required, owned, missingTotal, agrees };
  }

  // summarizeDeckDetail(detail) -> {
  //   cardKinds,    // distinct cards in the deck
  //   totalCards,   // sum of quantities
  //   missingKinds, // distinct cards the collection is short on
  //   curve,        // { "0": n, "1": n, ..., "7+": n } copies by mana value
  //   hasAnalysis,  // the engine has a stored analysis for this deck
  //   finalScore,   // analysis.final_score, or null
  // }
  function summarizeDeckDetail(detail) {
    const cards = detail && Array.isArray(detail.cards) ? detail.cards : [];
    const totalCards = cards.reduce((acc, c) => acc + (c.quantity || 0), 0);
    const missingKinds = cards.filter((c) => (c.missing || 0) > 0).length;
    const curve = {};
    for (const c of cards) {
      const mv = c.mana_value == null ? 0 : Math.floor(c.mana_value);
      const bucket = mv >= 7 ? "7+" : String(mv);
      curve[bucket] = (curve[bucket] || 0) + (c.quantity || 0);
    }
    const analysis = detail ? detail.analysis : null;
    return {
      cardKinds: cards.length,
      totalCards,
      missingKinds,
      curve,
      hasAnalysis: Boolean(analysis),
      finalScore: analysis ? analysis.final_score : null,
    };
  }

  exports.parityReport = parityReport;
  exports.deckMath = deckMath;
  exports.summarizeDeckDetail = summarizeDeckDetail;
})(typeof module !== "undefined" && module.exports ? module.exports : (window.decksLogic = {}));
