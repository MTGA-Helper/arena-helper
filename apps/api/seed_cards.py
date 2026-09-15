# -*- coding: utf-8 -*-
import asyncio
import gzip
import json
from datetime import datetime
import httpx
import structlog
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert
from database import AsyncSessionLocal
from models import Card, CardPrint, CardLegality

logger = structlog.get_logger(__name__)

async def seed_scryfall_cards():
    print("[+] Fetching Scryfall bulk data manifest...")
    headers = {"User-Agent": "ArenaHelperApp/1.0", "Accept": "*/*"}
    async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
        manifest_res = await client.get("https://api.scryfall.com/bulk-data")
        if manifest_res.status_code != 200:
            print(f"[-] Error: Scryfall API returned status code {manifest_res.status_code}")
            return
            
        manifest = manifest_res.json()
        download_uri = None
        for item in manifest.get("data", []):
            if item.get("type") == "default_cards":
                download_uri = item.get("jsonl_download_uri") or item.get("download_uri")
                break
        
        if not download_uri:
            print("[-] Error: Could not find a valid bulk download URI from Scryfall.")
            return

        print(f"[+] Downloading bulk card archive from {download_uri}...")
        async with client.stream("GET", download_uri) as response:
            if response.status_code != 200:
                print(f"[-] Error downloading archive: status {response.status_code}")
                return
            
            compressed_data = bytearray()
            async for chunk in response.aiter_bytes():
                compressed_data.extend(chunk)

    print("[+] Processing and parsing card objects...")
    # Safe decompression handling
    try:
        decompressed_bytes = gzip.decompress(compressed_data)
    except Exception:
        decompressed_bytes = bytes(compressed_data)

    lines = decompressed_bytes.splitlines()
    print(f"[+] Extracted {len(lines)} card lines. Executing oracle_id-anchored upsert...")

    async with AsyncSessionLocal() as session:
        count = 0
        dash_char = chr(8212)
        
        for line in lines:
            if not line.strip():
                continue
            try:
                rc = json.loads(line.decode("utf-8"))
            except Exception:
                continue

            oracle_id = rc.get("oracle_id")
            name = rc.get("name")
            if not oracle_id or not name:
                continue

            released_str = rc.get("released_at")
            released_date = None
            if released_str:
                try:
                    released_date = datetime.strptime(released_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            type_line = rc.get("type_line", "")
            base_types = type_line.split(dash_char)[0].strip().split() if dash_char in type_line else type_line.strip().split()

            # 1. Idempotent Upsert for Cards anchored on unique oracle_id
            stmt = insert(Card).values(
                oracle_id=oracle_id,
                name=name,
                oracle_text=rc.get("oracle_text"),
                mana_cost=rc.get("mana_cost"),
                mana_value=rc.get("cmv", rc.get("converted_mana_cost", 0.0)),
                colors=rc.get("colors", []),
                color_identity=rc.get("color_identity", []),
                types=base_types,
                keywords=rc.get("keywords", []),
                released_at=released_date
            ).on_conflict_do_update(
                index_elements=['oracle_id'],
                set_={
                    "name": name,
                    "oracle_text": rc.get("oracle_text"),
                    "mana_cost": rc.get("mana_cost"),
                    "mana_value": rc.get("cmv", rc.get("converted_mana_cost", 0.0)),
                    "colors": rc.get("colors", []),
                    "color_identity": rc.get("color_identity", []),
                    "types": base_types,
                    "keywords": rc.get("keywords", []),
                    "released_at": released_date
                }
            ).returning(Card.id)

            res = await session.execute(stmt)
            card_id = res.scalar()

            # 2. Idempotent Upsert for Card Prints (keyed on scryfall_id)
            print_stmt = insert(CardPrint).values(
                card_id=card_id,
                scryfall_id=rc.get("id"),
                set_code=rc.get("set", "unknown"),
                collector_number=rc.get("collector_number", "0"),
                rarity=rc.get("rarity", "common")
            ).on_conflict_do_update(
                index_elements=['scryfall_id'],
                set_={
                    "set_code": rc.get("set", "unknown"),
                    "collector_number": rc.get("collector_number", "0"),
                    "rarity": rc.get("rarity", "common")
                }
            )
            await session.execute(print_stmt)

            # 3. Idempotent Upsert for Card Legality (keyed on card_id)
            leg = rc.get("legalities", {})
            leg_stmt = insert(CardLegality).values(
                card_id=card_id,
                standard=(leg.get("standard") == "legal"),
                alchemy=(leg.get("alchemy") == "legal"),
                explorer=(leg.get("explorer") == "legal"),
                historic=(leg.get("historic") == "legal"),
                timeless=(leg.get("timeless") == "legal"),
                brawl=(leg.get("brawl") == "legal")
            ).on_conflict_do_update(
                index_elements=['card_id'],
                set_={
                    "standard": (leg.get("standard") == "legal"),
                    "alchemy": (leg.get("alchemy") == "legal"),
                    "explorer": (leg.get("explorer") == "legal"),
                    "historic": (leg.get("historic") == "legal"),
                    "timeless": (leg.get("timeless") == "legal"),
                    "brawl": (leg.get("brawl") == "legal")
                }
            )
            await session.execute(leg_stmt)

            count += 1
            if count % 500 == 0:
                await session.commit()
                print(f"[+] Upserted {count} cards...")

        await session.commit()
        print(f"[+] Successfully upserted {count} cards into PostgreSQL idempotently via oracle_id!")

if __name__ == "__main__":
    asyncio.run(seed_scryfall_cards())
