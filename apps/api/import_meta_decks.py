import asyncio
from datetime import datetime
from sqlalchemy import text
from database import AsyncSessionLocal

async def import_expanded_corpus_with_stats():
    print("[*] Starting Expanded Meta Deck Corpus Ingestion (Pipeline Validation Mode)...")
    
    total_decks_imported = 0
    cards_linked = 0
    cards_missing = 0
    missing_card_names = set()

    async with AsyncSessionLocal() as session:
        try:
            # 1. Clean out dev tables for a clean run
            print("[*] Clearing old test decks for a clean corpus rebuild...")
            await session.execute(text("DELETE FROM deck_cards;"))
            await session.execute(text("DELETE FROM decks;"))
            await session.commit()

            expanded_decks = [
                # --- STANDARD ---
                {
                    "name": "Mono-Red Aggro",
                    "format": "Standard",
                    "archetype": "Aggro",
                    "tier": 1,
                    "winrate": 57.3,
                    "meta_share": 12.4,
                    "source": "Untapped",
                    "source_url": "https://mtga.untapped.gg/meta",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Monstrous Rage": 4, "Slickshot Show-Off": 4, "Monastery Swiftspear": 4, "Play with Fire": 4}
                },
                {
                    "name": "Azorius Control",
                    "format": "Standard",
                    "archetype": "Control",
                    "tier": 1,
                    "winrate": 56.1,
                    "meta_share": 9.8,
                    "source": "Untapped",
                    "source_url": "https://mtga.untapped.gg/meta",
                    "last_seen": datetime.utcnow(),
                    "cards": {"No More Lies": 4, "Memory Deluge": 2, "The Wandering Emperor": 3, "Make Disappear": 3}
                },
                {
                    "name": "Dimir Midrange",
                    "format": "Standard",
                    "archetype": "Midrange",
                    "tier": 1,
                    "winrate": 56.8,
                    "meta_share": 10.5,
                    "source": "MTGGoldfish",
                    "source_url": "https://www.mtggoldfish.com/metagame/standard",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Deep-Cavern Bat": 4, "Gix, Yawgmoth Praetor": 2, "Scorn-Blade Berserker": 3, "Make Disappear": 2}
                },
                {
                    "name": "Boros Aggro",
                    "format": "Standard",
                    "archetype": "Aggro",
                    "tier": 2,
                    "winrate": 54.2,
                    "meta_share": 7.1,
                    "source": "Untapped",
                    "source_url": "https://mtga.untapped.gg/meta",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Resolute Reinforcements": 4, "Coppercoat Vanguard": 4, "Get Lost": 3}
                },
                {
                    "name": "Golgari Midrange",
                    "format": "Standard",
                    "archetype": "Midrange",
                    "tier": 2,
                    "winrate": 55.0,
                    "meta_share": 8.0,
                    "source": "MTGDecks",
                    "source_url": "https://mtgdecks.net/Standard",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Llanowar Loamspeaker": 4, "Preacher of the Schism": 4, "Gix's Command": 2}
                },

                # --- HISTORIC ---
                {
                    "name": "Izzet Wizards",
                    "format": "Historic",
                    "archetype": "Aggro",
                    "tier": 1,
                    "winrate": 58.4,
                    "meta_share": 11.2,
                    "source": "MTGGoldfish",
                    "source_url": "https://www.mtggoldfish.com/metagame/historic",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Consider": 4, "Dragon's Rage Channeler": 4, "Lightning Bolt": 4, "Wizard's Lightning": 4}
                },
                {
                    "name": "Rakdos Midrange",
                    "format": "Historic",
                    "archetype": "Midrange",
                    "tier": 1,
                    "winrate": 57.9,
                    "meta_share": 12.0,
                    "source": "Untapped",
                    "source_url": "https://mtga.untapped.gg/meta",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Thoughtseize": 4, "Fable of the Mirror-Breaker": 4, "Fatal Push": 4}
                },
                {
                    "name": "Azorius Auras",
                    "format": "Historic",
                    "archetype": "Aggro",
                    "tier": 2,
                    "winrate": 53.8,
                    "meta_share": 5.4,
                    "source": "AetherHub",
                    "source_url": "https://aetherhub.com/Metagame/Historic/",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Sram, Senior Edificer": 4, "All That Glitters": 4, "Light-Paws, Emperor's Voice": 4}
                },

                # --- EXPLORER ---
                {
                    "name": "Izzet Phoenix",
                    "format": "Explorer",
                    "archetype": "Combo",
                    "tier": 1,
                    "winrate": 58.1,
                    "meta_share": 13.5,
                    "source": "MTGGoldfish",
                    "source_url": "https://www.mtggoldfish.com/metagame/explorer",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Arclight Phoenix": 4, "Consider": 4, "Ledger Shredder": 4, "Treasure Cruise": 4}
                },
                {
                    "name": "Rakdos Vampires",
                    "format": "Explorer",
                    "archetype": "Midrange",
                    "tier": 1,
                    "winrate": 58.9,
                    "meta_share": 15.0,
                    "source": "Untapped",
                    "source_url": "https://mtga.untapped.gg/meta",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Vein Ripper": 4, "Sorin, Imperious Bloodlord": 4, "Thoughtseize": 4}
                },
                {
                    "name": "Mono-Green Devotion",
                    "format": "Explorer",
                    "archetype": "Ramp",
                    "tier": 2,
                    "winrate": 54.1,
                    "meta_share": 6.8,
                    "source": "MTGDecks",
                    "source_url": "https://mtgdecks.net/Explorer",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Llanowar Elves": 4, "Karn, the Great Creator": 4, "Nykthos, Shrine to Nyx": 4}
                },

                # --- TIMELESS ---
                {
                    "name": "Show and Tell Variants",
                    "format": "Timeless",
                    "archetype": "Combo",
                    "tier": 1,
                    "winrate": 60.2,
                    "meta_share": 16.4,
                    "source": "AetherHub",
                    "source_url": "https://aetherhub.com/Metagame/Timeless/",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Show and Tell": 4, "Omniscience": 4, "Brainstorm": 4, "Ponder": 4}
                },
                {
                    "name": "Domain Energy",
                    "format": "Timeless",
                    "archetype": "Midrange",
                    "tier": 1,
                    "winrate": 58.7,
                    "meta_share": 13.8,
                    "source": "MTGGoldfish",
                    "source_url": "https://www.mtggoldfish.com/metagame/timeless",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Guide of Souls": 4, "Ajani, Nacatl Pariah": 4, "Ocelot Pride": 4, "Lightning Bolt": 4}
                },

                # --- BRAWL ---
                {
                    "name": "Esika, God of the Tree (Commander)",
                    "format": "Brawl",
                    "archetype": "Ramp",
                    "tier": 1,
                    "winrate": 57.0,
                    "meta_share": 8.5,
                    "source": "MTGZone",
                    "source_url": "https://mtgzone.com/brawl/",
                    "last_seen": datetime.utcnow(),
                    "cards": {"Esika, God of the Tree": 1, "The Prismatic Bridge": 1, "Cultivate": 1, "Arcane Signet": 1}
                }
            ]

            for d in expanded_decks:
                deck_query = text("""
                    INSERT INTO decks (name, format, archetype, tier, winrate, meta_share, source, source_url, last_seen)
                    VALUES (:name, :format, :archetype, :tier, :winrate, :meta_share, :source, :source_url, :last_seen)
                    RETURNING id;
                """)
                res = await session.execute(deck_query, {
                    "name": d["name"],
                    "format": d["format"],
                    "archetype": d["archetype"],
                    "tier": d["tier"],
                    "winrate": d["winrate"],
                    "meta_share": d["meta_share"],
                    "source": d["source"],
                    "source_url": d["source_url"],
                    "last_seen": d["last_seen"]
                })
                deck_id = res.scalar()
                total_decks_imported += 1

                for card_name, qty in d["cards"].items():
                    card_res = await session.execute(text("SELECT id FROM cards WHERE name = :name LIMIT 1;"), {"name": card_name})
                    card_row = card_res.fetchone()
                    if card_row:
                        card_id = card_row.id
                        await session.execute(text("""
                            INSERT INTO deck_cards (deck_id, card_id, quantity)
                            VALUES (:deck_id, :card_id, :quantity)
                            ON CONFLICT DO NOTHING;
                        """), {"deck_id": deck_id, "card_id": card_id, "quantity": qty})
                        cards_linked += 1
                    else:
                        cards_missing += 1
                        missing_card_names.add(card_name)

            await session.commit()
            
            print("\n" + "="*40)
            print("--- IMPORT STATISTICS SUMMARY ---")
            print(f"  Imported Decks:  {total_decks_imported}")
            print(f"  Cards Linked:    {cards_linked}")
            print(f"  Cards Missing:   {cards_missing}")
            if missing_card_names:
                print(f"  Missing Cards:   {list(missing_card_names)}")
            print("========================================\n")

        except Exception as e:
            await session.rollback()
            print(f"[!] Error during expanded bulk import: {e}")

if __name__ == "__main__":
    asyncio.run(import_expanded_corpus_with_stats())