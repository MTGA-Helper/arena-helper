"""
Next Action Service - Recommendation Engine V2.5 Baseline with V2.6 Incremental Simulation
"""
import math

def calculate_roi_score(completion_gain, cost, rarity):
    # Stabilized V2.5 ROI formula (frozen baseline)
    normalized_gain = completion_gain / max(cost, 1)
    return normalized_gain * 1000.0

async def get_next_action():
    # V2.6 Incremental Simulation Options
    # simulation_options = [1, min(2, deficit), deficit]
    
    # Placeholder example evaluating candidate: Resolute Reinforcements
    card_name = "Resolute Reinforcements"
    rarity = "Rare"
    cost = 1  # Will be dynamically calculated from deficit in full loop
    completion_gain = 2.0  # e.g., 92.0% -> 94.0%
    
    roi_score = calculate_roi_score(completion_gain, cost, rarity)
    roi_per_wc = roi_score / cost

    return {
        "action_type": "CRAFT",
        "card_name": card_name,
        "cost": cost,
        "rarity": rarity,
        "roi_score": round(roi_score, 1),
        "roi_per_wc": round(roi_per_wc, 1),
        "confidence": "LOW",
        "reason": [
            "Advances Boros Aggro completion (92.0% -> 94.0%)",
            f"Requires only {cost} Rare wildcard(s)",
            f"V2.5 Optimized ROI per WC ({round(roi_per_wc, 1)})",
            "Playable immediately upon crafting"
        ],
        "impact": {
            "unlocks": [
                "Boros Aggro"
            ]
        }
    }
