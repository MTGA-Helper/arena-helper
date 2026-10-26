"""
Next Action Service - V2.6 Milestone B3 (Card-Level Resolution via /recommendations/decks)

REPAIR (Oct 26, 2026 — Phase 0 engine fixes): this deployed copy under
apps/api/ never received the Oct 16 B3 bridge repair (commit 0bac155) —
that fix landed only in the legacy repo-root services/ twin, which
production does not run (render.yaml starts apps.api.main). This copy
still called the hardcoded http://127.0.0.1:8000 loopback, which never
reaches the service on Render (Render assigns the port via PORT), so
every production call failed and the endpoint silently served the
hardcoded Boros Aggro fallback. fetch_live_candidates() below is the
Oct 16 repaired implementation, transplanted unchanged in behavior.
"""
import math
import os
import httpx

def calculate_roi_score(completion_gain, cost, rarity):
    # =====================================================
    # STRICT V2.5 FROZEN BASELINE SCORING ENGINE
    # =====================================================
    normalized_gain = completion_gain / max(cost, 1)
    return normalized_gain * 1000.0

async def fetch_live_candidates():
    """
    Milestone B3 Bridge (repaired Oct 16, 2026; transplanted into this
    deployed apps/api copy Oct 26, 2026): Pulls this service's own
    /recommendations/decks payload and derives card-level deficits from the
    missing_cards each deck already carries.

    The original bridge called http://127.0.0.1:8000/api/recommendations
    (route does not exist; port is wrong on Render, which assigns PORT)
    and then /api/upgrade/{deck-name} (that route expects an engine slug,
    not a display name). Every call failed in production, the candidate
    list came back empty, and the endpoint silently served the hardcoded
    fallback below. Locally the same failure was masked during service
    tests that exercised get_next_action with live local data.
    """
    candidates = []
    try:
        port = os.environ.get("PORT", "8000")
        base = "http://" + "127.0.0.1" + ":" + str(port)
        async with httpx.AsyncClient() as client:
            resp = await client.get(base + "/recommendations/decks")
            if resp.status_code == 200:
                decks = resp.json()

                for deck_item in decks[:5]:  # Inspect top 5 recommendation candidates
                    deck_name = deck_item.get("deck_name")
                    completion = deck_item.get("completion_percent", 0.0)

                    if completion < 100.0 and deck_name:
                        base_gain = max(0.5, (100.0 - completion) / 10.0)

                        for mc in deck_item.get("missing_cards", []):
                            c_name = mc.get("name")
                            deficit = mc.get("quantity", 1)
                            rarity = mc.get("rarity", "rare").lower()

                            candidates.append({
                                "deck_name": deck_name,
                                "card_name": c_name,
                                # Slice 4 (Oct 26, 2026): common candidates
                            # pass through as common now that the deck
                            # tally prices all four rarities — the old
                            # whitelist silently re-labeled every
                            # common as a rare.
                            # "rarity": rarity if rarity in ["rare", "mythic", "uncommon"] else "rare",
                            "rarity": rarity if rarity in ["rare", "mythic", "uncommon", "common"] else "rare",
                                "deficit": deficit,
                                "base_completion_gain": base_gain
                            })

    except Exception as e:
        print(f"Error fetching live candidates: {e}")

    if candidates:
        return candidates

    # Fallback safety default
    return [
        {
            "deck_name": "Boros Aggro (Fallback)",
            "card_name": "Resolute Reinforcements",
            "rarity": "rare",
            "deficit": 4,
            "base_completion_gain": 2.0
        }
    ]

async def get_next_action():
    candidates = await fetch_live_candidates()

    best_recommendation = None
    best_overall_roi_per_wc = -1.0
    evaluated_summary = []

    for candidate in candidates:
        deficit = candidate["deficit"]
        simulation_options = sorted(list({
            1,
            min(2, deficit),
            deficit
        }))

        card_name = candidate["card_name"]
        rarity = candidate["rarity"]
        deck_name = candidate["deck_name"]
        base_gain = candidate["base_completion_gain"]

        for opt_cost in simulation_options:
            simulated_gain = base_gain * (opt_cost / 1.0)
            roi_score = calculate_roi_score(simulated_gain, opt_cost, rarity)
            roi_per_wc = roi_score / opt_cost

            evaluated_summary.append(f"{card_name} ({deck_name}) [Cost: {opt_cost}] -> ROI/WC: {round(roi_per_wc, 1)}")

            if roi_per_wc > best_overall_roi_per_wc:
                best_overall_roi_per_wc = roi_per_wc
                best_recommendation = {
                    "action_type": "CRAFT",
                    "card_name": card_name,
                    "cost": opt_cost,
                    "rarity": rarity.capitalize(),
                    "roi_score": round(roi_score, 1),
                    "roi_per_wc": round(best_overall_roi_per_wc, 1),
                    "confidence": "LOW",
                    "reason": [
                        f"Advances {deck_name} completion via card-level upgrade feed",
                        f"Milestone B3 Evaluated options for {card_name}: {simulation_options}",
                        f"Optimal Craft Increment Selected: {opt_cost} {rarity.capitalize()}(s)",
                        f"V2.5 Scoring Baseline ROI per WC ({round(best_overall_roi_per_wc, 1)})",
                        "Playable immediately upon crafting"
                    ],
                    "impact": {
                        "unlocks": [
                            deck_name
                        ],
                        "all_evaluated_options": evaluated_summary
                    }
                }

    return best_recommendation
