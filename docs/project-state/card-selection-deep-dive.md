# Card Selection Deep Dive — charter (Oct 17, 2026)
Billy's own branch: **feature/card-selection**, cut from dev @ 6a494b2.
His call: card selection + collection.py is "the whole part no one can do
right yet." He's right — it's the heart of the product. Everything else
(ingestion, decks API, telemetry) exists to serve this.

## What "right" means (the standard)
Given a collection and a goal, selection must produce picks a master would
defend: **legal → owned or craftable → role & curve sound → synergy-aware →
proven consistent → explained.** This morning's mono-red build (by hand, by
the team) is the method proof: legality killed the famous netdeck first
(rotation), ownership came from the real collection file, wildcard math was
exact, a goldfish simulation was the consistency oracle, and traps were
excluded by synergy reasoning (Hazoret's max-speed gate, Magebane Lizard's
anti-synergy). The deep dive encodes THAT pipeline in code.

## Already on this branch (from dev)
- `apps/api/collection.py` (7.0 KB) + `collection_importer.py` (4.2 KB) —
  the current collection layer; audit first: what does it actually model?
- `apps/api/craft_priority.py` (5.3 KB) — wildcard/craft logic seed.
- `apps/api/deck_analysis.py`, `deck_unlock_report.py` — analysis surfaces.
- `apps/api/engine_graph.db` (528 KB) — Platform B, the SQLite knowledge
  graph, checked in on dev.
- Data in Neon: cards 38,906 · prints 118,527 · legalities 38,906 ·
  tags 13,458 · collections 12,960. Synergies = 0 in prod, BUT the
  derivation is built on feature/synergy-derivation-v1 @ 646f872
  (dry-run default, --write fills only derived: rows) — merge or
  cherry-pick it in as the synergy substrate.
- Collection ground truth for testing: Billy's Oct 12 export
  (18,977 rows; 4,753 owned names; 15,266 copies).

## Known gaps to dig at
1. synergies table empty in prod; derivation unexecuted even on dev Neon.
2. wildcard_inventories = 0 — craft math runs on assumptions until real.
3. match_histories = 0 — no outcome data yet (PlayerLogTail.txt on the PC,
   3.7 MB, is the archaeology source).
4. Name-resolution gap seen live: "Hearth Elemental" unknown to the
   analyzer — selection is only as good as card identity resolution.
5. Collection freshness: the Oct 12 CSV is the test fixture, not a feed.

## Working rules (unchanged, Matt's topology)
- This branch lives off dev; PRs go to dev, never main.
- Dry-run by default; --write touches derived data only; tests beside code.
- Muse reviews diffs on request; Billy's instincts lead the design.

## First moves (Billy's session)
1. Read collection.py end to end; write down what it models vs what it
   should (one page in docs/project-state/).
2. Decide the selection pipeline's shape: Legal → Owned/Craftable → Role/
   Curve → Synergy → Simulate → Explain — which stage is code, which is data?
3. Pick the first vertical slice: e.g. "given my collection, list every
   Standard-legal playable I own in a chosen archetype, ranked, with
   reasons" — the query this morning's build answered by hand.

---

## ADDENDUM — Billy's drill-down spec (Oct 17, 14:38)
Billy's words: "Why this card? Not just why this card — why this card IN
THIS DECK, and why 60 cards. Simulate matches, understand mana, and learn
to manipulate the game with enchantments, instants, abilities, and
sorceries." His example: a 1/1 that gains +1, whose enchantment adds
+1/+1 — "now it's a 3/3 for one mana and one card. Aggressive start."

### The Why Stack — every selection answers five questions
1. **Why this card** (vacuum): rate — stats/effects per mana vs the field.
2. **Why in THIS deck**: role + named synergy links (who it feeds, who
   feeds it). A card with no links is a suspect, however good its rate.
3. **Why this count**: 4-of = "want it every game, early"; 2-of = tutor
   target, legendary, or high-variance. Counts are probabilities, not vibes.
4. **Why now**: legality window + meta position (what it beats today).
5. **The cut test**: what specifically breaks if it's removed? If nothing
   breaks, it doesn't belong.

### Why exactly 60
60 is the format MINIMUM, and minimum is optimal by dilution math: every
card above 60 lowers the draw probability of your best cards (hypergeo-
metric) while adding nothing the 60 didn't already say. Exceptions must
PAY for their dilution (e.g. an 80-card companion shell). Inside the 60,
the land count is a curve-matching decision proven by simulation (our
mono-red: 20 lands → 0.39 avg mulligans, 1.0% brick rate over 3,000 games),
never folklore ratios.

### Mana as a system, not a count
Selection scores mana three ways: SOURCES (can the deck cast its spells
on curve, color pips included), CURVE (mana spent every turn = tempo),
SEQUENCE (play order as a decision tree — hold the instant, fire the
sorcery on schedule). Flood/screw rates are measured outputs of the sim.

### Manipulation taxonomy — cards as state transformations
Billy's 3/3-for-one-mana example is the core insight: evaluate the STACK,
not the card. Instants = timing windows (tricks, responses, reach held
open). Sorceries = on-schedule power (efficiency for speed of use).
Enchantments/auras = persistent modifiers that re-rate every creature
they touch. Abilities (prowess, valiant, triggered pings) = engines that
convert other cards into value. A selection engine must model: base card
→ modified state → what the opponent must now spend to answer it.

### The simulation ladder
- Rung 1 GOLDFISH (done for mono-red): your clock, consistency, mulligans.
- Rung 2 SCRIPTED OPPONENT: removal on curve, blockers, a sweeper — the
  rung that answers the Manifold Mouse question goldfish couldn't.
- Rung 3 ARCHETYPE GAUNTLET: mirror, control, midrange; Bo3 + sideboard
  plans; mulligan policy per matchup.
Each rung exists because the previous one cannot see its questions.

### Reference implementation (mono-red, this morning)
- Emberheart Challenger: prowess AND valiant — Ancestral Anger triggers
  both = pump + card draw + card draw for {R}. Three jobs, one mana.
- Ancestral Anger: cantrip that is also a prowess trigger and a valiant
  enabler; replaces itself, so its floor is "free trigger."
- Slickshot Show-Off: plot lets you deploy off-curve, then a spell burst
  turns it into +2/+0 per spell — the deck's burst finisher.
- 20 Mountain, zero nonbasics: Rockface Village rejected because its red
  mana casts creature spells only — it would strand the burn/cantrip
  suite. A land is a selection too, and it answers the Why Stack.
