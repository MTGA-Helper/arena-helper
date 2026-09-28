import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def generate_meta_stats():
    print("[*] Starting Meta Card Statistics Generation (Pipeline Validation)...")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Clear existing stats for a clean run
            await session.execute(text("DELETE FROM meta_card_stats;"))
            await session.commit()

            # 2. Aggregate appearances and compute meta-share weighted win rates
            aggregation_query = text("""
                WITH format_deck_counts AS (
                    SELECT format, COUNT(DISTINCT id) AS total_format_decks
                    FROM decks
                    GROUP BY format
                ),
                card_appearances AS (
                    SELECT 
                        d.format,
                        dc.card_id,
                        COUNT(DISTINCT d.id) AS decks_played,
                        -- Meta-share weighted average win rate (falling back to simple AVG if meta_share is null)
                        COALESCE(
                            SUM(d.winrate * COALESCE(d.meta_share, 1.0)) / NULLIF(SUM(COALESCE(d.meta_share, 1.0)), 0),
                            AVG(d.winrate)
                        ) AS weighted_win_rate
                    FROM decks d
                    JOIN deck_cards dc ON dc.deck_id = d.id
                    GROUP BY d.format, dc.card_id
                )
                INSERT INTO meta_card_stats (card_id, format, appearance_rate, winrate, decks_played)
                SELECT 
                    ca.card_id,
                    ca.format,
                    (ca.decks_played::float / fdc.total_format_decks) * 100 AS appearance_rate,
                    ca.weighted_win_rate AS winrate,
                    ca.decks_played
                FROM card_appearances ca
                JOIN format_deck_counts fdc ON fdc.format = ca.format;
            """)

            await session.execute(aggregation_query)
            await session.commit()
            print("[+] Meta card statistics successfully generated!")

            # 3. Query row counts to confirm success
            count_res = await session.execute(text("SELECT COUNT(*) FROM meta_card_stats;"))
            total_stats = count_res.scalar()
            print(f"[+] Total MetaCardStat rows created: {total_stats}")

            # 4. Print top appearance stats sample
            result = await session.execute(text("""
                SELECT c.name, m.format, m.decks_played, m.appearance_rate, m.winrate
                FROM meta_card_stats m
                JOIN cards c ON c.id = m.card_id
                ORDER BY m.appearance_rate DESC
                LIMIT 20;
            """))
            rows = result.fetchall()
            print("\n--- Top Meta Cards Sample ---")
            for r in rows:
                print(f"Card: {r.name:<25} | Format: {r.format:<10} | Decks: {r.decks_played} | Appearance: {r.appearance_rate:.1f}% | Weighted WR: {r.winrate:.1f}%")

        except Exception as e:
            await session.rollback()
            print(f"[!] Error generating meta stats: {e}")

if __name__ == "__main__":
    asyncio.run(generate_meta_stats())