// Desktop API client smoke test (plain Node, no Electron).
//
//   node test/api-smoke.js
//
// Uses ARENA_API_BASE (default: production engine). Modes:
//  - read-only checks (health, decks, collection reconciliation) always run;
//  - ARENA_SMOKE_BASELINE=1 adds the production baseline gate: the signed-in
//    collection must hold exactly 12,960 unique cards (the Oct 26, 2026
//    ingestion baseline the TURBO surge reconciles against);
//  - the auth round-trip runs only when ARENA_SMOKE_AUTH=1, and must only be
//    pointed at a LOCAL api instance — it creates a throwaway account.
//    Never run the auth leg against production;
//  - the Slice 3 decks parity leg (the Phase 0 gate's 14 decks, plus
//    the owned+missing==required invariant on every deck) runs against
//    any engine, read-only — skipped in fixture mode and when
//    ARENA_SMOKE_DECKS=0;
//  - the Slice 3 fixture legs run only when ARENA_SMOKE_DECKS_FIXTURE=1
//    against a LOCAL api seeded by test/decks_fixture.py, and assert
//    the hand-computed deck/detail/analysis values printed there.
//    ARENA_SMOKE_NEW_DECK=1 adds the phase-2 leg: a deck seeded after
//    the first pass appears in the list with its analysis.
//  - the collection upload round-trip runs only when ARENA_SMOKE_UPLOAD=1,
//    and must only be pointed at a LOCAL api instance seeded by
//    test/collection_fixture.py — uploading REPLACES the collection.
//    Never run the upload leg against production or the dev service.
//  - the Slice 4 Jund Dino acceptance leg runs only when
//    ARENA_SMOKE_JUND=1, pointed at a LOCAL api seeded by
//    test/jund_fixture.py (a scratch clone of the full corpus):
//    Matt's deck must cost exactly 41 wildcards = 10M/25R/5U/1C
//    through the app's own client + recommendationsLogic, and the
//    next-action answer must be a real Jund candidate.
//  - the Slice 5 watcher legs run only when ARENA_SMOKE_WATCHER=1,
//    against a LOCAL api seeded by test/collection_fixture.py then
//    test/watcher_fixture.py: the Player.log fixtures in
//    test/fixtures/ are built from REAL log lines (real decks, real
//    grpIds, real inventory values), and the legs prove the parse,
//    the live tail (append, split line, rotation), and the sync
//    round-trip into the API. Run the watcher legs LAST in a fixture
//    session: the sync moves the fixture wildcards 7/3 -> 9/14.

const { ApiClient } = require("../api");
const { summarizeCollection } = require("../renderer/collectionLogic");
const { parityReport, deckMath, summarizeDeckDetail } = require("../renderer/decksLogic");
const { wildcardBill, billText, nextActionView } = require("../renderer/recommendationsLogic");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { createState, feedLine, buildPayload } = require("../watcherParse");
const { LogWatcher } = require("../watcher");

const RUN_AUTH = process.env.ARENA_SMOKE_AUTH === "1";
const RUN_UPLOAD = process.env.ARENA_SMOKE_UPLOAD === "1";
const RUN_BASELINE = process.env.ARENA_SMOKE_BASELINE === "1";
const RUN_DECKS_FIXTURE = process.env.ARENA_SMOKE_DECKS_FIXTURE === "1";
const RUN_NEW_DECK = process.env.ARENA_SMOKE_NEW_DECK === "1";
const RUN_JUND = process.env.ARENA_SMOKE_JUND === "1";
const RUN_WATCHER = process.env.ARENA_SMOKE_WATCHER === "1";

// The Phase 0 live gate's deck list (Oct 26, 2026): production's 14
// decks, verified name-for-name. The parity leg asserts the engine
// still serves exactly this set. (The gate summary shortened the
// first deck to "Esika Commander"; the engine's stored name is the
// full "Esika, God of the Tree (Commander)" — the constant uses the
// engine's name, caught by this leg's first live run.)
const EXPECTED_DECK_NAMES = [
  "Esika, God of the Tree (Commander)", "Rakdos Midrange",
  "Mono-Green Devotion",
  "Dimir Midrange", "Izzet Phoenix", "Mono-Red Aggro", "Azorius Auras",
  "Show and Tell Variants", "Izzet Wizards", "Boros Aggro",
  "Rakdos Vampires", "Domain Energy", "Azorius Control",
  "Golgari Midrange",
];
const BASELINE_UNIQUE_CARDS = 12960; // Oct 26, 2026 ingestion baseline

let failures = 0;

function check(name, cond, detail = "") {
  console.log((cond ? "PASS" : "FAIL") + " - " + name + (detail ? " " + detail : ""));
  if (!cond) failures++;
}

// Each leg is isolated: a thrown error fails that leg, never aborts the run.
async function leg(name, fn) {
  try {
    await fn();
  } catch (e) {
    check(name, false, "(" + e.message + ")");
  }
}

// The Slice 2 fixture CSVs — must match test/collection_fixture.py.
// CSV #1: a duplicate Alpha row (merges to x4), one unmatched card.
const FIXTURE_CSV_1 = [
  "Name,Quantity,Set",
  "Fixture Alpha,3,FIX",
  "Fixture Alpha,1,FIX",
  "Fixture Beta,2,FIX",
  "Fixture Gamma,4,FIX",
  "Fixture Delta,1,FIX",
  "Nonexistent Card,5,XXX",
  "",
].join("\n");
// CSV #2: replacement upload — the collection becomes just Gamma x1.
const FIXTURE_CSV_2 = "Name,Quantity,Set\nFixture Gamma,1,FIX\n";

function rowsByName(list) {
  const map = {};
  for (const item of list) map[item.name] = item.quantity;
  return map;
}

(async () => {
  const api = new ApiClient();
  console.log("API base:", api.base);

  await leg("health ok", async () => {
    const health = await api.health();
    check("health ok", health && health.status === "healthy", JSON.stringify(health));
  });

  if (process.env.ARENA_SMOKE_DECKS === "0") {
    console.log("SKIP - decks (ARENA_SMOKE_DECKS=0; local fixture has no card corpus)");
  } else if (RUN_JUND) {
    console.log("SKIP - live decks parity (Jund mode asserts its own deck)");
  } else if (RUN_DECKS_FIXTURE) {
    console.log("SKIP - live decks parity (fixture mode asserts its own deck list)");
  } else {
    await leg("decks parity with the Phase 0 gate list", async () => {
      const decks = await api.decks();
      const parity = parityReport(decks, EXPECTED_DECK_NAMES);
      check("decks parity: exactly the 14 gate decks", parity.complete && parity.count === 14,
        JSON.stringify(parity));
      const bad = decks.filter((d) => !deckMath(d).agrees).map((d) => d.deck_name);
      check("decks math: owned + missing == required on every deck", bad.length === 0,
        bad.length ? "disagree: " + bad.join(", ") : "14/14 agree");
    });
  }

  await leg("bad login is rejected", async () => {
    try {
      await api.login("nobody@example.com", "wrong-password");
      check("bad login is rejected", false, "login unexpectedly succeeded");
    } catch (e) {
      check("bad login is rejected", e.status === 401, "(" + e.message + ")");
    }
  });

  if (RUN_AUTH) {
    await leg("auth round-trip", async () => {
      // Fixture addresses use example.com: the API's EmailStr validation
      // rejects special-use TLDs such as .invalid with a 422.
      const email = "slice1-smoke+" + Date.now() + "@example.com";
      // Throwaway smoke credential for the local instance only; never a real account.
      const pw = "smoke-" + Date.now();
      const reg = await api.register(email, pw);
      // The register endpoint answers 201 {"message": "User created
      // successfully"} — a resolved promise here already means success.
      check("register accepted (201)", Boolean(reg && (reg.message || reg.email || reg.id)),
        JSON.stringify(reg).slice(0, 120));
      const login = await api.login(email, pw);
      check("login returns a token", Boolean(login && login.access_token));
      check("client holds the token after login", Boolean(api.token));
      api.logout();
      check("logout clears the token", api.token === null);
    });
  } else {
    console.log("SKIP - auth round-trip (set ARENA_SMOKE_AUTH=1 against a LOCAL api)");
  }

  // --- Slice 2: collection -------------------------------------------

  await leg("collection list reconciles with stats", async () => {
    const [list, stats] = await Promise.all([api.collection(), api.collectionStats()]);
    const s = summarizeCollection(list, stats);
    check("collection list reconciles with stats", s.allAgree,
      "rows=" + s.rowCount + " qty=" + s.qtySum +
      " stats: unique=" + stats.unique_cards + " total=" + stats.total_cards);
    // Observation only on shared engines: pre-promotion code still serves
    // fan-out rarity counts there (rares+mythics can exceed the total).
    // The invariant itself is asserted in the upload leg, where the fixed
    // code runs against the hand-built fixture.
    console.log("INFO - rarity from stats: rares=" + stats.rares + " mythics=" + stats.mythics +
      " (sum " + (stats.rares + stats.mythics) + " vs total " + stats.total_cards + ")");
  });

  if (RUN_BASELINE) {
    await leg("baseline: 12,960 unique cards", async () => {
      const [list, stats] = await Promise.all([api.collection(), api.collectionStats()]);
      check("baseline: stats.unique_cards is 12,960", stats.unique_cards === BASELINE_UNIQUE_CARDS,
        "got " + stats.unique_cards);
      check("baseline: list holds 12,960 rows", list.length === BASELINE_UNIQUE_CARDS,
        "got " + list.length);
    });
  } else {
    console.log("SKIP - baseline gate (set ARENA_SMOKE_BASELINE=1 against production)");
  }

  if (RUN_UPLOAD) {
    await leg("collection upload round-trip + stats hand-check", async () => {
      const up1 = await api.uploadCollectionCsv(FIXTURE_CSV_1, "fixture-1.csv");
      check("upload #1 summary", up1.cards_imported === 11 && up1.unique_cards === 4 &&
        up1.matched_cards === 5 && up1.unmatched_cards === 1 && up1.duplicates === 1,
        JSON.stringify(up1));

      const list1 = await api.collection();
      const byName = rowsByName(list1);
      check("collection after upload #1",
        list1.length === 4 && byName["Fixture Alpha"] === 4 && byName["Fixture Beta"] === 2 &&
        byName["Fixture Gamma"] === 4 && byName["Fixture Delta"] === 1,
        JSON.stringify(byName));

      const stats1 = await api.collectionStats();
      // Hand-check (collection_fixture.py): Alpha's canonical print is
      // rare, so its 4 copies count as rares ONCE each — the Phase 0 fix.
      // The pre-fix fan-out query would report rares=8, mythics=6 here.
      check("stats after upload #1 (rarity fix hand-check)",
        stats1.total_cards === 11 && stats1.unique_cards === 4 &&
        stats1.rares === 4 && stats1.mythics === 2 &&
        stats1.wildcards.rare === 7 && stats1.wildcards.mythic === 3,
        JSON.stringify(stats1));

      const up2 = await api.uploadCollectionCsv(FIXTURE_CSV_2, "fixture-2.csv");
      check("upload #2 summary (replacement)", up2.cards_imported === 1 && up2.unique_cards === 1,
        JSON.stringify(up2));
      const list2 = await api.collection();
      const stats2 = await api.collectionStats();
      check("collection replaced by upload #2",
        list2.length === 1 && list2[0].name === "Fixture Gamma" && list2[0].quantity === 1 &&
        stats2.total_cards === 1 && stats2.unique_cards === 1 &&
        stats2.rares === 0 && stats2.mythics === 0,
        "list=" + JSON.stringify(list2) + " stats=" + JSON.stringify(stats2));

      await api.uploadCollectionCsv(FIXTURE_CSV_1, "fixture-1.csv");
      const stats3 = await api.collectionStats();
      check("re-upload restores the full fixture",
        stats3.total_cards === 11 && stats3.unique_cards === 4 &&
        stats3.rares === 4 && stats3.mythics === 2,
        JSON.stringify(stats3));
    });
  } else {
    console.log("SKIP - upload round-trip (set ARENA_SMOKE_UPLOAD=1 against a LOCAL fixture api)");
  }


  // --- Slice 3: decks fixture legs (LOCAL fixture api only) ---------

  if (RUN_DECKS_FIXTURE) {
    const near = (a, b, eps) => Math.abs(a - b) <= eps;

    await leg("fixture Deck A: list math + detail + stored analysis", async () => {
      const decks = await api.decks();
      const a = decks.find((d) => d.deck_name === "Fixture Dino Tribal");
      check("fixture list holds Deck A with its id", Boolean(a && a.deck_id === 3001),
        JSON.stringify(a && { deck_id: a.deck_id, deck_name: a.deck_name }));
      // Slice 4: the bill now tallies ALL FOUR rarities — Bolt's
      // 2 uncommon are counted (the pre-Slice-4 shape dropped them
      // silently) — and missing_cards carry craft rarities.
      check("fixture Deck A list math", Boolean(a) &&
        a.cards_required === 14 && a.cards_owned === 10 &&
        a.completion_percent === 71.4 &&
        a.wildcard_cost.rare === 2 && a.wildcard_cost.mythic === 0 &&
        a.wildcard_cost.uncommon === 2 && a.wildcard_cost.common === 0 &&
        wildcardBill(a.wildcard_cost).total === 4 &&
        billText(a.wildcard_cost) === "4 wildcards — 2 rare · 2 uncommon" &&
        deckMath(a).agrees,
        JSON.stringify(a));

      const detail = await api.deckDetail(3001);
      const s = summarizeDeckDetail(detail);
      check("fixture Deck A detail totals", s.cardKinds === 4 && s.totalCards === 14 &&
        s.missingKinds === 2 && s.curve["0"] === 4 && s.curve["1"] === 6 && s.curve["4"] === 4,
        JSON.stringify(s));
      const byName = {};
      for (const c of detail.cards) byName[c.name] = c;
      // The Slice 3 seed fix, visible end-to-end: subtypes + full type
      // line come back on the card rows.
      check("fixture Deck A subtypes served (seed fix)", Boolean(byName["Fixture Dino"]) &&
        byName["Fixture Dino"].subtypes.includes("Dinosaur") &&
        byName["Fixture Dino"].type_line === "Creature \u2014 Dinosaur" &&
        byName["Fixture Land"].subtypes.includes("Forest") &&
        byName["Fixture Elf"].subtypes.join(" ") === "Elf Druid",
        JSON.stringify(byName["Fixture Dino"]));
      check("fixture Deck A per-card owned/missing", Boolean(byName["Fixture Bolt"]) &&
        byName["Fixture Bolt"].owned === 0 && byName["Fixture Bolt"].missing === 2 &&
        byName["Fixture Dino"].owned === 2 && byName["Fixture Dino"].missing === 2,
        JSON.stringify(byName["Fixture Bolt"]));
      // Hand-computed in test/decks_fixture.py from the engine's own
      // metric definitions: meta 40.0 / mana 95.0 / synergy 0 /
      // consistency 75.0 / final 45.25 — served exactly as stored.
      const an = detail.analysis;
      check("fixture Deck A analysis as stored", Boolean(an) &&
        near(an.meta_score, 40.0, 0.02) && near(an.mana_score, 95.0, 0.02) &&
        near(an.synergy_score, 0.0, 0.02) && near(an.consistency_score, 75.0, 0.02) &&
        near(an.final_score, 45.25, 0.02) && s.hasAnalysis && near(s.finalScore, 45.25, 0.02),
        JSON.stringify(an));
    });

    if (RUN_NEW_DECK) {
      await leg("fixture Deck B: newly seeded deck appears with analysis", async () => {
        const decks = await api.decks();
        const b = decks.find((d) => d.deck_name === "Fixture Wurm Ramp");
        check("fixture list holds the new Deck B", Boolean(b && b.deck_id === 3002),
          "decks=" + decks.map((d) => d.deck_name).join(", "));
        check("fixture Deck B list math", Boolean(b) &&
          b.cards_required === 11 && b.cards_owned === 8 &&
          b.completion_percent === 72.7 &&
          b.wildcard_cost.rare === 0 && b.wildcard_cost.mythic === 3 &&
          b.wildcard_cost.uncommon === 0 && b.wildcard_cost.common === 0 &&
          deckMath(b).agrees,
          JSON.stringify(b));
        const detail = await api.deckDetail(3002);
        check("fixture Deck B analysis present after refresh", Boolean(detail.analysis) &&
          Math.abs(detail.analysis.final_score - 42.62) <= 0.05,
          JSON.stringify(detail.analysis));
      });
    } else {
      console.log("SKIP - new-deck leg (set ARENA_SMOKE_NEW_DECK=1 after decks_fixture.py --phase2)");
    }
  }

  // --- Slice 4: Jund Dino acceptance leg (LOCAL Jund api only) ----

  if (RUN_JUND) {
    await leg("JUND ACCEPTANCE: 41 wildcards = 10M/25R/5U/1C via the app client", async () => {
      const decks = await api.decks();
      const jund = decks.find((d) => d.deck_name === "Jund Dino Madness");
      check("jund deck served by the recommendations list", Boolean(jund),
        "decks=" + decks.map((d) => d.deck_name).join(", "));
      const bill = wildcardBill(jund && jund.wildcard_cost);
      check("jund bill is exactly 41 = 10M/25R/5U/1C",
        bill.mythic === 10 && bill.rare === 25 && bill.uncommon === 5 &&
        bill.common === 1 && bill.total === 41,
        JSON.stringify(bill));
      check("jund bill text is the spec's sentence",
        billText(jund && jund.wildcard_cost) ===
          "41 wildcards — 10 mythic · 25 rare · 5 uncommon · 1 common",
        billText(jund && jund.wildcard_cost));
      check("jund totals: 71 required / 30 owned / 42.3% / math ties out",
        Boolean(jund) && jund.cards_required === 71 && jund.cards_owned === 30 &&
        jund.completion_percent === 42.3 && deckMath(jund).agrees,
        JSON.stringify(jund && { r: jund.cards_required, o: jund.cards_owned, p: jund.completion_percent }));

      const detail = await api.deckDetail(jund.deck_id);
      const byName = {};
      for (const c of detail.cards) byName[c.name] = c;
      check("jund detail craft rarities (cheapest print)",
        byName["Fabled Passage"].craft_rarity === "rare" &&
        byName["Cavern of Souls"].craft_rarity === "rare" &&
        byName["Seize the Spoils"].craft_rarity === "common" &&
        byName["Bitter Triumph"].craft_rarity === "uncommon" &&
        byName["Gishath, Sun's Avatar"].craft_rarity === "mythic",
        JSON.stringify(["Fabled Passage", "Cavern of Souls", "Seize the Spoils", "Bitter Triumph"]
          .map((n) => n + "=" + (byName[n] || {}).craft_rarity)));
      check("jund detail basics are free (missing 0, basic flag)",
        ["Mountain", "Forest", "Swamp"].every((n) =>
          byName[n] && byName[n].missing === 0 && byName[n].basic === true),
        JSON.stringify(["Mountain", "Forest", "Swamp"].map((n) => byName[n])));
    });

    await leg("next-action serves a real Jund candidate", async () => {
      const na = await api.nextAction();
      const v = nextActionView(na);
      check("next-action available and NOT the fallback",
        v.available && !v.isFallback && v.deckName === "Jund Dino Madness",
        JSON.stringify(v));
      const decks = await api.decks();
      const jund = decks.find((d) => d.deck_name === "Jund Dino Madness");
      const missingNames = new Set((jund.missing_cards || []).map((m) => m.name));
      check("next-action card is one of the deck's missing cards",
        missingNames.has(v.cardName), String(v.cardName));
    });
  }


  // --- Slice 5: Arena Watcher legs (LOCAL fixture api only) --------

  if (RUN_WATCHER) {
    const fixtureLogPath = path.join(__dirname, "fixtures", "Player.log");
    const session2Path = path.join(__dirname, "fixtures", "Player-session2.log");
    const readLines = (p) => fs.readFileSync(p, "utf8").split("\n").filter((l) => l.length > 0);
    const parseFile = (p) => {
      const state = createState();
      for (const line of readLines(p)) feedLine(state, line);
      return state;
    };
    const waitFor = async (fn, ms = 6000) => {
      const t0 = Date.now();
      while (Date.now() - t0 < ms) {
        if (fn()) return true;
        await new Promise((r) => setTimeout(r, 120));
      }
      return fn();
    };
    const copies = (d) => d.cards.reduce((a, c) => a + c.quantity, 0);

    await leg("watcher parse: fixture log yields the real decks + inventory", async () => {
      const state = parseFile(fixtureLogPath);
      const payload = buildPayload(state);
      const byName = {};
      for (const d of payload.decks) byName[d.name] = d;
      check("payload holds exactly the 2 real library decks (precon placeholder skipped)",
        payload.decks.length === 2 && Boolean(byName["Killsquad"]) && Boolean(byName["Jeskai Artifacts (4)"]),
        payload.decks.map((d) => d.name).join(", "));
      check("Killsquad: 12 rows / 60 copies (real log values)",
        byName["Killsquad"].cards.length === 12 && copies(byName["Killsquad"]) === 60,
        JSON.stringify({ rows: byName["Killsquad"].cards.length, copies: copies(byName["Killsquad"]) }));
      check("Jeskai Artifacts (4): 20 rows / 61 copies (dump + EventSetDeckV3 merged)",
        byName["Jeskai Artifacts (4)"].cards.length === 20 && copies(byName["Jeskai Artifacts (4)"]) === 61,
        JSON.stringify({ rows: byName["Jeskai Artifacts (4)"].cards.length, copies: copies(byName["Jeskai Artifacts (4)"]) }));
      check("inventory from the real snapshot: gold 3675, gems 3020, vault 419, WC 194/189/9/14",
        payload.inventory.gold === 3675 && payload.inventory.gems === 3020 &&
        payload.inventory.vault_progress === 419 &&
        payload.inventory.wildcards.common === 194 && payload.inventory.wildcards.uncommon === 189 &&
        payload.inventory.wildcards.rare === 9 && payload.inventory.wildcards.mythic === 14,
        JSON.stringify(payload.inventory));
      check("robustness counters: 1 malformed line counted, 2 course sightings counted",
        state.stats.malformed === 1 && state.stats.coursesSeen === 2,
        JSON.stringify(state.stats));
    });

    await leg("watcher parse: adversarial lines never throw", async () => {
      const state = createState();
      let threw = false;
      try {
        feedLine(state, "{not json at all");
        feedLine(state, "");
        feedLine(state, '{"InventoryInfo":{"SeqId":2,"Changes":[]');
        feedLine(state, "x".repeat(3 * 1024 * 1024));
        feedLine(state, "[UnityCrossThreadLogger]==> EventSetDeckV3 {bad");
      } catch { threw = true; }
      check("malformed/partial/huge lines are absorbed, never thrown", !threw);
      check("the 2 sentinel-bearing bad lines are counted malformed",
        state.stats.malformed === 2, JSON.stringify(state.stats));
    });

    await leg("watcher tail: live append, split line, rotation reset", async () => {
      const tmpLog = path.join(os.tmpdir(), "arena-watcher-smoke-" + process.pid + ".log");
      fs.copyFileSync(fixtureLogPath, tmpLog);
      const watcher = new LogWatcher({ logPath: tmpLog, pollMs: 100 });
      watcher.start();
      try {
        check("tail catches up with the existing log",
          await waitFor(() => Object.keys(watcher.getState().decks).length >= 2),
          JSON.stringify(watcher.getStatus()));
        const s2dump = JSON.parse(readLines(session2Path).find((l) => l.includes('"DeckSummaries"')));
        fs.appendFileSync(tmpLog, JSON.stringify({ InventoryInfo: s2dump.InventoryInfo }) + "\n");
        check("appended inventory lands (gold 3675 -> 3925, the real session-2 value)",
          await waitFor(() => watcher.getState().inventory && watcher.getState().inventory.gold === 3925));
        const coursesLine = readLines(fixtureLogPath).find((l) => l.startsWith('{"Courses"'));
        const seenBefore = watcher.getState().stats.coursesSeen;
        const cut = Math.floor(coursesLine.length / 2);
        fs.appendFileSync(tmpLog, coursesLine.slice(0, cut));
        await new Promise((r) => setTimeout(r, 450));
        check("a split line is NOT parsed before its newline",
          watcher.getState().stats.coursesSeen === seenBefore,
          "coursesSeen=" + watcher.getState().stats.coursesSeen);
        fs.appendFileSync(tmpLog, coursesLine.slice(cut) + "\n");
        check("the completed line parses",
          await waitFor(() => watcher.getState().stats.coursesSeen === seenBefore + 1));
        fs.writeFileSync(tmpLog, fs.readFileSync(session2Path, "utf8"));
        check("rotation/truncation resets state to the new session",
          await waitFor(() => watcher.getStatus().rotations >= 1 &&
            Object.keys(watcher.getState().decks).length === 1),
          JSON.stringify(watcher.getStatus()));
        const p2 = buildPayload(watcher.getState());
        check("post-rotation payload is the session-2 deck only (Mono-Blue Elementals, 13 rows / 56 copies)",
          p2.decks.length === 1 && p2.decks[0].name === "Mono-Blue Elementals" &&
          p2.decks[0].cards.length === 13 && copies(p2.decks[0]) === 56,
          JSON.stringify(p2.decks.map((d) => d.name)));
      } finally {
        watcher.stop();
        fs.rmSync(tmpLog, { force: true });
      }
    });

    await leg("watcher sync round-trip lands in the API (fixture stack)", async () => {
      const payload = buildPayload(parseFile(fixtureLogPath));
      const summary = await api.syncWatcher(payload);
      check("sync summary: 2 decks, 32 rows, 31 matched, 1 unmatched (grp 75587 unregistered on purpose)",
        summary.decks_stored === 2 && summary.card_rows === 32 &&
        summary.cards_matched === 31 && summary.cards_unmatched === 1 &&
        summary.wildcards_updated === true,
        JSON.stringify(summary));
      const decks = await api.watcherDecks();
      const byName = {};
      for (const d of decks) byName[d.name] = d;
      check("read-back holds both decks",
        decks.length === 2 && Boolean(byName["Killsquad"]) && Boolean(byName["Jeskai Artifacts (4)"]),
        decks.map((d) => d.name).join(", "));
      check("Killsquad read-back: 12 cards, all resolved to fixture names",
        byName["Killsquad"].cards.length === 12 &&
        byName["Killsquad"].cards.every((c) => c.name === "Watcher Fixture Card " + c.grp_id),
        JSON.stringify(byName["Killsquad"].cards.slice(0, 3)));
      const unreg = byName["Jeskai Artifacts (4)"].cards.find((c) => c.grp_id === 75587);
      check("the unregistered grpId is stored raw with a null name, not dropped",
        Boolean(unreg) && unreg.name === null && unreg.quantity >= 1,
        JSON.stringify(unreg));
      const stats = await api.collectionStats();
      check("wildcard inventory moved to the log's values (rare 9, mythic 14)",
        stats.wildcards.rare === 9 && stats.wildcards.mythic === 14,
        JSON.stringify(stats.wildcards));
      const again = await api.syncWatcher(payload);
      const decks2 = await api.watcherDecks();
      check("re-sync replaces, never duplicates (still 2 decks, same counts)",
        again.decks_stored === 2 && again.cards_matched === 31 && decks2.length === 2,
        JSON.stringify(again));
    });
  } else {
    console.log("SKIP - watcher legs (set ARENA_SMOKE_WATCHER=1 against a LOCAL fixture api)");
  }

  console.log("RESULT:", failures === 0 ? "ALL PASS" : failures + " FAILURES");
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => {
  console.error("SMOKE ERROR:", e.message);
  process.exit(1);
});
