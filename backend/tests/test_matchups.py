from app.analytics import build_matchups


def row(match_id, my_deck, opponent, result, on_play):
    return (match_id, my_deck, opponent, result, on_play)


def test_matchups_aggregate_results_and_play_draw_stats():
    result = build_matchups([
        row("1", "Aggro", "Control", "win", True),
        row("2", "Aggro", "Control", "loss", False),
        row("3", "Aggro", "Control", "draw", True),
        row("4", "Aggro", "Control", None, False),
    ])
    matchup = result.matchups[0]
    assert matchup.matches == 4
    assert matchup.rated_matches == 2
    assert matchup.winrate == 0.5
    assert matchup.on_play.matches == 2
    assert matchup.on_play.winrate == 1.0
    assert matchup.on_draw.matches == 2
    assert matchup.on_draw.losses == 1
    assert matchup.on_draw.winrate == 0.0


def test_matchups_filter_and_deterministic_order():
    rows = [
        row("1", "Aggro", "Zulu", "win", True),
        row("2", "Aggro", "Alpha", "loss", True),
        row("3", "Control", "Alpha", "win", False),
    ]
    assert [item.opponent_deck for item in build_matchups(rows).matchups] == [
        "Alpha",
        "Zulu",
    ]
    filtered = build_matchups(rows, " Aggro ")
    assert filtered.deck == "Aggro"
    assert filtered.total_matchups == 2
    assert [item.opponent_deck for item in filtered.matchups] == ["Alpha", "Zulu"]


def test_matchups_empty_rows_and_empty_filter_are_deterministic():
    assert build_matchups([], "").dict() == {
        "deck": None,
        "total_matchups": 0,
        "matchups": [],
    }
