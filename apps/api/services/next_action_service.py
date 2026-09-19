from sqlalchemy import text
from database import AsyncSessionLocal

async def get_next_action():
    async with AsyncSessionLocal() as session:
        # 1. Fetch user ID
        user_res = await session.execute(text("SELECT id FROM users LIMIT 1;"))
        user_row = user_res.fetchone()
        if not user_row:
            return {"error": "No user found"}
        user_id = str(user_row.id)

        # 2. Fetch user collection
        col_res = await session.execute(text("SELECT card_id, quantity FROM user_collections WHERE user_id::text = :uid;"), {"uid": user_id})
        user_collection = {row.card_id: row.quantity for row in col_res.fetchall()}

        # 3. Fetch wildcard inventory
        available_rares, available_mythics = 20, 8
        wc_res = await session.execute(text("SELECT rare, mythic FROM wildcard_inventories WHERE user_id::text = :uid LIMIT 1;"), {"uid": user_id})
        wc_row = wc_res.fetchone()
        if wc_row:
            available_rares = wc_row.rare or 20
            available_mythics = wc_row.mythic or 8

        # 4. Fetch all decks and their analysis scores
        decks_res = await session.execute(text("""
            SELECT d.id, d.name, d.format, da.final_score
            FROM decks d
            JOIN deck_analyses da ON da.deck_id = d.id;
        """))
        decks = decks_res.fetchall()

        card_opportunities = {}

        for deck in decks:
            deck_id = deck.id
            deck_name = deck.name
            deck_score = deck.final_score or 50.0

            cards_res = await session.execute(text("""
                SELECT c.id, c.name, dc.quantity, cp.rarity
                FROM deck_cards dc
                JOIN cards c ON c.id = dc.card_id
                LEFT JOIN card_prints cp ON cp.card_id = c.id
                WHERE dc.deck_id = :did;
            """), {"did": int(deck_id)})
            deck_cards = cards_res.fetchall()

            total_required = sum(dc.quantity for dc in deck_cards)
            if total_required == 0:
                continue

            owned_count = 0
            deck_card_deficits = {}

            for dc in deck_cards:
                user_owned = user_collection.get(dc.id, 0)
                needed = dc.quantity
                if user_owned >= needed:
                    owned_count += needed
                else:
                    owned_count += user_owned
                    deficit = needed - user_owned
                    rarity = (dc.rarity or "rare").lower()
                    is_mythic = any(m in rarity for m in ["mythic", "special", "masterpiece"])
                    card_rarity = "Mythic" if is_mythic else "Rare"

                    deck_card_deficits[dc.id] = {
                        "card_name": dc.name,
                        "rarity": card_rarity,
                        "deficit": deficit
                    }

            current_completion = (owned_count / total_required) * 100.0

            for cid, info in deck_card_deficits.items():
                if cid not in card_opportunities:
                    card_opportunities[cid] = {
                        "card_name": info["card_name"],
                        "rarity": info["rarity"],
                        "decks": {},
                        "total_cost": 0
                    }
                
                simulated_owned = owned_count + info["deficit"]
                simulated_completion = (simulated_owned / total_required) * 100.0
                completion_gain = simulated_completion - current_completion
                completes_deck = simulated_completion >= 99.9

                card_opportunities[cid]["decks"][deck_id] = {
                    "deck_name": deck_name,
                    "deficit": info["deficit"],
                    "deck_score": deck_score,
                    "completion_gain": round(completion_gain, 1),
                    "completes_deck": completes_deck,
                    "before_pct": round(current_completion, 1),
                    "after_pct": round(simulated_completion, 1)
                }

        for cid, info in card_opportunities.items():
            max_deficit = max([d["deficit"] for d in info["decks"].values()])
            info["total_cost"] = max_deficit

        # 5. Recommendation Engine V2.2 Scoring & Player-Psychology Gates
        best_action = None
        highest_roi = -1.0

        for cid, info in card_opportunities.items():
            cost = info["total_cost"]
            
            # Wildcard inventory hard bounds check
            if info["rarity"] == "Mythic" and cost > available_mythics:
                continue
            if info["rarity"] == "Rare" and cost > available_rares:
                continue

            cumulative_meta = sum(d["deck_score"] for d in info["decks"].values())
            total_completion_gain = sum(d["completion_gain"] for d in info["decks"].values())
            max_after_pct = max([d["after_pct"] for d in info["decks"].values()])
            completes_any = any(d["completes_deck"] for d in info["decks"].values())

            # Tiered Completion Threshold Multiplier (Matches player value of playable decks)
            if max_after_pct >= 99.0:
                completion_multiplier = 30.0
            elif max_after_pct >= 95.0:
                completion_multiplier = 15.0
            elif max_after_pct >= 90.0:
                completion_multiplier = 5.0
            else:
                completion_multiplier = 1.0

            # Wildcard Efficiency: Reward high gain per wildcard spent
            efficiency = total_completion_gain / max(1, cost)

            # Core V2.2 ROI Formula
            roi_score = (cumulative_meta * total_completion_gain * completion_multiplier * efficiency) / (cost ** 1.2)

            # "Would I Do This?" Anti-Pattern Penalty Gate (Heavy penalty for expensive crafts with tiny gains)
            if cost >= 4 and total_completion_gain < 5.0 and not completes_any:
                roi_score *= 0.1

            if roi_score > highest_roi:
                highest_roi = roi_score
                primary_impact = list(info["decks"].values())[0]
                primary_deck = primary_impact["deck_name"]
                before = primary_impact["before_pct"]
                after = primary_impact["after_pct"]

                confidence = "HIGH" if completes_any or (cost == 1 and total_completion_gain > 5) else ("MEDIUM" if total_completion_gain > 10 else "LOW")

                reasons = []
                if completes_any:
                    reasons.append(f"Completes {primary_deck} immediately ({before}% -> {after}%)")
                else:
                    reasons.append(f"Advances {primary_deck} completion ({before}% -> {after}%)")
                
                reasons.append(f"Requires only {cost} {info['rarity']} wildcard(s)")
                reasons.append(f"Highest calculated V2.2 ROI score ({round(roi_score, 1)})")
                reasons.append("Playable immediately upon crafting")

                best_action = {
                    "action_type": "CRAFT",
                    "card_name": info["card_name"],
                    "cost": cost,
                    "rarity": info["rarity"],
                    "roi_score": round(roi_score, 1),
                    "confidence": confidence,
                    "reason": reasons,
                    "impact": {
                        "unlocks": [d["deck_name"] for d in info["decks"].values()]
                    }
                }

        if not best_action:
            return {"action_type": "SAVE", "confidence": "HIGH", "reason": ["No immediate high-ROI crafts available within current wildcard inventory bounds."]}

        return best_action