# Analytics

Analytics reads only normalized `MatchHistory` columns:
`match_id`, `my_deck`, `opponent_deck`, `match_result`, and `on_play`. It never
queries `raw_payload`, so parser-specific fields cannot affect results.

## Overview

`GET /analytics/overview` returns totals, overall rated winrate, favorite and
best deck, and per-deck performance.

```json
{
  "total_matches": 12,
  "rated_matches": 10,
  "overall_winrate": 0.6,
  "favorite_deck": "Mono Red",
  "best_deck": "Control",
  "deck_performance": [
    {"deck": "Control", "matches": 4, "wins": 3, "losses": 1, "winrate": 0.75}
  ]
}
```

`total_matches` counts every MatchHistory row. `rated_matches` is wins plus
losses only. Draws and null results count as matches but are excluded from
winrate denominators. Empty data returns zero values, null deck selections, and
an empty performance list.

## Matchups

`GET /analytics/matchups` aggregates by normalized `opponent_deck`.
Optionally filter by the normalized `my_deck` label:
`GET /analytics/matchups?my_deck=Mono%20Red`.

```json
{
  "deck": "Mono Red",
  "total_matchups": 2,
  "matchups": [
    {
      "opponent_deck": "Control",
      "matches": 5,
      "wins": 3,
      "losses": 1,
      "rated_matches": 4,
      "winrate": 0.75,
      "on_play": {"matches": 3, "wins": 2, "losses": 0, "winrate": 1.0},
      "on_draw": {"matches": 2, "wins": 1, "losses": 1, "winrate": 0.5}
    }
  ]
}
```

Matchups are sorted by `rated_matches` descending and then
`opponent_deck` ascending. All rows count toward `matches`; only wins and
losses count toward rated winrates. A missing or blank filter is treated as no
filter. Empty results return the requested deck, `total_matchups: 0`, and an
empty `matchups` list.
