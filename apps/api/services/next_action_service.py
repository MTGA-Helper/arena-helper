"""
Next Action Service - V2.6 Milestone B3 (Card-Level Resolution via /recommendations/decks)
"""
import math
import httpx

def calculate_roi_score(completion_gain, cost, rarity):
    # =====================================================
    # STRICT V2.5 FROZEN BASELINE SCORING ENGINE
    # =====================================================
    normalized_gain = completion_gain / max(cost, 1)
    return normalized_gain * 1000.0

async def fetch_live_candidates():
    """
    Milestone B3 Bridge: Pulls deck recommendations from /recommendations/decks
    and extracts card-level missing deficits directly with proper rarity filtering.
    """
    candidates = []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/recommendations/decks")
            if resp.status_code == 200:
                decks = resp.json()
                if isinstance(decks, list):
                    for deck_item in decks[:5]:
                        deck_name = deck_item.get("deck_name")
                        completion = deck_item.get("completion_percent", 0.0)
                        missing_cards = deck_item.get("missing_cards", [])
                        base_gain = max(0.5, (100.0 - completion) / 10.0)

                        for mc in missing_cards:
                            c_name = mc.get("name")
                            deficit = mc.get("quantity", 1)
                            rarity = mc.get("rarity", "rare").lower()
                            if rarity not in ("rare", "mythic", "uncommon"):
                                continue

                            candidates.append({
                                "deck_name": deck_name,
                                "card_name": c_name,
                                "rarity": rarity,
                                "deficit": deficit,
                                "base_completion_gain": base_gain
                            })
    except Exception as e:
        import traceback
        print(f"Error fetching live candidates: {repr(e)}")
        traceback.print_exc()

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
