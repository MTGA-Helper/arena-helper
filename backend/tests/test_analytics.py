from app.analytics import build_overview


def row(match_id, deck, result):
    return (match_id, deck, result)


def test_overview_counts_wins_losses_draws_and_null_results():
    overview = build_overview([
        row("1", "Aggro", "win"),
        row("2", "Aggro", "loss"),
        row("3", "Control", "draw"),
        row("4", "Control", None),
    ])

    assert overview.total_matches == 4
    assert overview.rated_matches == 2
    assert overview.overall_winrate == 0.5
    assert [(item.deck, item.matches, item.wins, item.losses) for item in overview.deck_performance] == [
        ("Aggro", 2, 1, 1),
        ("Control", 2, 0, 0),
    ]


def test_overview_aggregates_decks_and_uses_deterministic_ties():
    overview = build_overview([
        row("1", {"name": "Bravo"}, "win"),
        row("2", {"name": "Alpha"}, "win"),
        row("3", {"name": "Bravo"}, "loss"),
        row("4", {"name": "Alpha"}, "loss"),
    ])

    assert overview.favorite_deck == "Alpha"
    assert overview.best_deck == "Alpha"


def test_overview_empty_dataset_is_deterministic():
    overview = build_overview([])

    assert overview.total_matches == 0
    assert overview.rated_matches == 0
    assert overview.overall_winrate == 0.0
    assert overview.favorite_deck is None
    assert overview.best_deck is None
    assert overview.deck_performance == []
