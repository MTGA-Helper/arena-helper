# Arena Helper - Recommendation Engine V2.5

## Root Cause Analysis

### Bug #1 - Cost and Simulation Are Out Of Sync

Current recommendation:

Card: Gix, Yawgmoth Praetor
Cost: 1 Mythic
Completion: 72.7% -> 97.0%

Problem:

A single mythic craft causing a 24.3% completion jump suggests one of:

1. The deck is only missing Gix.
2. The simulation is crafting multiple copies but reporting cost = 1.
3. The same deficit is being counted multiple times.

Action:

Verify:

Displayed Cost
==
Simulated Wildcards Spent

Audit variables:

- craft_amount
- deficit
- max_deficit
- total_cost

Add temporary diagnostics:

print(
    f"CARD={info['card_name']}, "
    f"COST={cost}, "
    f"DEFICIT={info['deficit']}, "
    f"BEFORE={current_completion}, "
    f"AFTER={after_completion}"
)

Success Criteria:

Craft Cost
==
Simulation Cost

for every recommendation.

---

### Bug #2 - ROI Explosion

Current formula:

roi_score =
(
    cumulative_meta *
    total_completion_gain *
    tier_bonus *
    efficiency
) / (cost ** 1.1)

Issue:

tier_bonus and efficiency multiply together.

Example:

- Meta ≈ 56.8
- Completion Gain ≈ 24.3
- Tier Bonus ≈ 50
- Efficiency ≈ 24.3
- Cost ≈ 1

Result:

ROI ≈ 596,247

Scores become impossible to interpret.

---

## Proposed V2.5 Formula

base_score =
(
    cumulative_meta *
    normalized_gain *
    efficiency
)

milestone_bonus = {
    0: 0,
    1: 50,
    2: 200,
    3: 500
}.get(max_tier_jump, 0)

roi_score = base_score + milestone_bonus

Benefits:

- Scores stay understandable
- Tier jumps remain important
- No runaway multipliers
- Easier benchmark comparisons

---

## Optional Gain Normalization

Option A:

completion_gain = min(
    after_completion - current_completion,
    25.0
)

Option B (preferred):

normalized_gain =
(
    after_completion -
    current_completion
) / 100.0

This prevents completion gains from dominating ROI.

---

## Benchmark Status

| Version | Card | Cost | Before | After | Tier Jump | Verdict |
|----------|----------|----------|----------|----------|----------|----------|
| V2.1 | Gix | 8 Mythics | 72.7% | 75.8% | No | NO |
| V2.2 | Gix | 8 Mythics | 72.7% | 75.8% | No | NO |
| V2.3 | Resolute Reinforcements | 1 Rare | 92.0% | 94.0% | No | MAYBE |
| V2.4 | Gix | 1 Mythic | 72.7% | 97.0% | Yes | MAYBE |

---

## V2.5 Goals

✅ Verify Craft Cost Matches Simulation

✅ Remove ROI Explosions

✅ Normalize Milestone Bonuses

✅ Audit Gix Recommendation

✅ Validate Against Benchmark

---

## Release Theme

V2.5 = Consistency and Calibration

Not:

- New Endpoints
- New Features

Instead:

- Accurate Simulation
- Accurate Cost Accounting
- Trustworthy Recommendations

Once simulation cost and displayed cost agree,
Arena Helper can begin producing benchmark-worthy
YES recommendations.