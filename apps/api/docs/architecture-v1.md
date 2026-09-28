# Arena Helper Architecture Specification (v1.0)

## Core Identity & Uniqueness Rules
- **Card Uniqueness:** Anchored entirely on Scryfall's `oracle_id`. Functional rule evaluations, synergies, and meta statistics map to the canonical oracle card, not individual printings.
- **Print Uniqueness:** Anchored on `scryfall_id` (`CardPrint`).
- **Collection Ownership:** Tracked against canonical `Card` references per user.
- **Import Resolution Strategy:** 
  1. Primary match via `arena_id` (when present from MTGA logs/exports).
  2. Fallback match via Exact Name + Set Code (`name + set_code`).

## Database Schema Layers
1. **Truth Layer:** Scryfall ingestion, legalities, printings, and keywords.
2. **Meta Layer:** Ingested tournament lists from platforms like [Untapped.gg](https://untapped.gg/) and [MTGGoldfish](https://www.mtggoldfish.com/), tracking staple rates and tier distributions.
3. **Graph Layer:** Directed-acyclic synergy edges (`CardSynergy`) scoped by format with explicit confidence scores and negative conflict values (`-1.0` to `1.0`).
4. **Optimization Layer:** Collection completion, wildcard deficit calculation, and expected winrate-per-wildcard returns.
