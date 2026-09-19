"""
Next Action Service - V2.6 Strict Single-Variable Incremental Simulation
"""
import math

def calculate_roi_score(completion_gain, cost, rarity):
    # =====================================================
    # FROZEN V2.5 BASELINE SCORING FORMULA (DO NOT ALTER)
    # =====================================================
    # Exact V2.5 normalization and weighting logic
    normalized_gain = completion_gain / max(cost, 1)
    return normalized_gain * 1000.0

async def get_next_action():
    # =====================================================
    # V2.6 EXPERIMENT: SINGLE VARIABLE CHANGE ONLY
    # =====================================================
    deficit = 4  # Example deck deficit
    simulation_options = [
        1,
        min(2, deficit),
        deficit
    ]
    
    card_name = "Resolute Reinforcements"
    rarity = "Rare"
    base_completion_gain = 2.0  # 92.0% -> 94.0%
    
    best_cost = simulation_options[0]
    best_roi_per_wc = -1.0
    best_roi_score = 0.0

    for opt_cost in simulation_options:
        simulated_gain = base_completion_gain * (opt_cost / 1.0)
        
        # Evaluated strictly using the FROZEN V2.5 scoring engine
        roi_score = calculate_roi_score(simulated_gain, opt_cost, rarity)
        roi_per_wc = roi_score / opt_cost
        
        if roi_per_wc > best_roi_per_wc:
            best_roi_per_wc = roi_per_wc
            best_cost = opt_cost
            best_roi_score = roi_score

    return {
        "action_type": "CRAFT",
        "card_name": card_name,
        "cost": best_cost,
        "rarity": rarity,
        "roi_score": round(best_roi_score, 1),
        "roi_per_wc": round(best_roi_per_wc, 1),
        "confidence": "LOW",
        "reason": [
            "Advances Boros Aggro completion (92.0% -> 94.0%)",
            f"V2.6 Incremental Simulation evaluated options: {simulation_options}",
            f"Optimal Craft Increment Selected: {best_cost} Wildcard(s)",
            f"V2.5 Frozen Baseline ROI per WC ({round(best_roi_per_wc, 1)})",
            "Playable immediately upon crafting"
        ],
        "impact": {
            "unlocks": [
                "Boros Aggro"
            ]
        }
    }
