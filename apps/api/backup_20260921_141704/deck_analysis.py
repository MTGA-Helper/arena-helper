import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def analyze_decks():
    print("[*] Starting Deck Structural Analysis (Phase 2.3)...")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Clear existing analyses for a clean run
            await session.execute(text("DELETE FROM deck_analyses;"))
            await session.commit()

            # 2. Fetch all decks with their metadata
            decks_res = await session.execute(text("SELECT id, name, format, archetype, winrate, meta_share FROM decks;"))
            decks = decks_res.fetchall()

            if not decks:
                print("[!] No decks found in corpus to analyze.")
                return

            analyzed_count = 0

            for deck in decks:
                deck_id = deck.id
                winrate = deck.winrate or 50.0
                meta_share = deck.meta_share or 5.0

                # 3. Fetch all cards and quantities for this specific deck, along with mana value and tags
                cards_res = await session.execute(text("""
                    SELECT c.id, c.name, c.mana_value, dc.quantity,
                           (SELECT COUNT(*) FROM card_tags ct WHERE ct.card_id = c.id) as tag_count
                    FROM deck_cards dc
                    JOIN cards c ON c.id = dc.card_id
                    WHERE dc.deck_id = :deck_id;
                """), {"deck_id": deck_id})
                deck_cards = cards_res.fetchall()

                if not deck_cards:
                    continue

                total_cards = sum(dc.quantity for dc in deck_cards)
                
                # --- METRIC 1: META SCORE ---
                # Scaled blend of winrate and meta share
                meta_score = min(100.0, max(0.0, (winrate * 0.7) + (meta_share * 0.3)))

                # --- METRIC 2: MANA SCORE ---
                # Calculate average mana value (cmv) weighted by quantity
                total_cmv = sum((dc.mana_value or 2.0) * dc.quantity for dc in deck_cards)
                avg_cmv = total_cmv / total_cards if total_cards > 0 else 3.0
                
                # Ideal aggressive/midrange curve sits around 2.0 - 2.8. Penalize overly high or low curves.
                if 2.0 <= avg_cmv <= 3.2:
                    mana_score = 95.0
                elif avg_cmv < 2.0:
                    mana_score = 85.0
                else:
                    mana_score = max(40.0, 95.0 - ((avg_cmv - 3.2) * 15.0))

                # --- METRIC 3: SYNERGY SCORE ---
                # Evaluate tag density across cards as a proxy for functional synergy
                total_tags_matched = sum(dc.tag_count * dc.quantity for dc in deck_cards)
                tag_density = total_tags_matched / total_cards if total_cards > 0 else 0
                synergy_score = min(100.0, tag_density * 25.0)  # Normalized scaling

                # --- METRIC 4: CONSISTENCY SCORE ---
                # Rewarding decks that maximize 4x playsets vs random singletons
                four_ofs = sum(1 for dc in deck_cards if dc.quantity >= 4)
                unique_cards = len(deck_cards)
                redundancy_ratio = (four_ofs / unique_cards) if unique_cards > 0 else 0
                consistency_score = min(100.0, redundancy_ratio * 100.0)

                # --- FINAL SCORE ---
                final_score = (
                    meta_score * 0.40 +
                    synergy_score * 0.25 +
                    consistency_score * 0.20 +
                    mana_score * 0.15
                )

                # 4. Insert into deck_analyses table
                await session.execute(text("""
                    INSERT INTO deck_analyses (deck_id, meta_score, synergy_score, consistency_score, mana_score, final_score)
                    VALUES (:deck_id, :meta_score, :synergy_score, :consistency_score, :mana_score, :final_score)
                    ON CONFLICT DO NOTHING;
                """), {
                    "deck_id": deck_id,
                    "meta_score": round(meta_score, 2),
                    "synergy_score": round(synergy_score, 2),
                    "consistency_score": round(consistency_score, 2),
                    "mana_score": round(mana_score, 2),
                    "final_score": round(final_score, 2)
                })

                analyzed_count += 1
                print(f"  [Analyzed] {deck.name:<30} | Final Score: {final_score:.1f} (Meta: {meta_score:.1f}, Syn: {synergy_score:.1f}, Con: {consistency_score:.1f}, Mana: {mana_score:.1f})")

            await session.commit()
            print(f"\n[+] Successfully analyzed and scored {analyzed_count} decks!")

        except Exception as e:
            await session.rollback()
            print(f"[!] Error during deck analysis: {e}")

if __name__ == "__main__":
    asyncio.run(analyze_decks())