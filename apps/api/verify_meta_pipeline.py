import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def verify_pipeline():
    print("[*] Running Extended Meta Pipeline Verification...")
    async with AsyncSessionLocal() as session:
        try:
            tables = [
                "cards",
                "decks",
                "deck_cards",
                "match_histories",
                "card_tags",
                "card_synergies",
                "meta_card_stats",
                "deck_analyses",
                "user_collections",
                "wildcard_inventories"
            ]
            
            print("\n--- Database Row Counts ---")
            for table in tables:
                try:
                    res = await session.execute(text(f"SELECT COUNT(*) FROM {table};"))
                    count = res.scalar()
                    print(f"  {table}: {count}")
                except Exception as e:
                    print(f"  {table}: [Table Missing or Error]")

            # Sample Decks Check
            print("\n--- Sample Decks ---")
            deck_res = await session.execute(text("SELECT name, format FROM decks LIMIT 5;"))
            deck_rows = deck_res.fetchall()
            if deck_rows:
                for dr in deck_rows:
                    print(f"  Deck: {dr.name} ({dr.format})")
            else:
                print("  [No decks found]")

            # Sample Deck-Cards Relationship Check
            print("\n--- Sample Deck Cards (Foreign Key Check) ---")
            dc_res = await session.execute(text("""
                SELECT c.name, dc.quantity, d.name as deck_name
                FROM deck_cards dc
                JOIN cards c ON c.id = dc.card_id
                JOIN decks d ON d.id = dc.deck_id
                LIMIT 10;
            """))
            dc_rows = dc_res.fetchall()
            if dc_rows:
                for dcr in dc_rows:
                    print(f"  [{dcr.deck_name}] {dcr.name} x{dcr.quantity}")
            else:
                print("  [No deck-card relations found]")

            print("\n---------------------------")
            print("[+] Verification complete!")

        except Exception as e:
            print(f"[!] Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(verify_pipeline())