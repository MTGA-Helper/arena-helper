# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import delete, func
import csv
import io
from uuid import UUID

from apps.api.database import AsyncSessionLocal
from apps.api.models import UserCollection, Card, CardPrint, WildcardInventory

router = APIRouter(prefix="/collection", tags=["Collection"])

# Dummy current user dependency for Phase 1 testing
async def get_current_user_id() -> UUID:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserCollection.user_id).limit(1))
        user_id = result.scalars().first()
        if not user_id:
            # Fallback test UUID if no user collections exist yet
            from apps.api.models import User
            user_res = await session.execute(select(User).limit(1))
            user = user_res.scalars().first()
            if user:
                return user.id
            raise HTTPException(status_code=404, detail="No users found in database.")
        return user_id

@router.post("/upload")
async def upload_collection(file: UploadFile = File(...), user_id: UUID = Depends(get_current_user_id)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a CSV file.")

    content = await file.read()
    decoded = content.decode("utf-8", errors="ignore")
    csv_reader = csv.DictReader(io.StringIO(decoded))
    rows = list(csv_reader)

    matched_cards = 0
    unmatched_cards = 0
    duplicates = 0
    imported_rows = 0
    unique_set = set()
    collected_quantities = {}

    async with AsyncSessionLocal() as session:
        print("[*] Preloading card prints and cards into memory for O(1) resolution...")
        print_res = await session.execute(select(CardPrint.scryfall_id, CardPrint.card_id).where(CardPrint.scryfall_id != None))
        scryfall_map = {row[0].lower(): row[1] for row in print_res.all() if row[0]}

        print_set_res = await session.execute(
            select(Card.name, CardPrint.set_code, Card.id)
            .join(CardPrint, Card.id == CardPrint.card_id)
        )
        name_set_map = {(row[0].lower(), row[1].lower()): row[2] for row in print_set_res.all() if row[0] and row[1]}

        card_res = await session.execute(select(Card.name, Card.id))
        name_map = {row[0].lower(): row[1] for row in card_res.all() if row[0]}

        print(f"[*] Preloaded {len(scryfall_map)} scryfall IDs, {len(name_set_map)} name+set pairs, and {len(name_map)} card names.")

        for row in rows:
            imported_rows += 1
            name = row.get("Name") or row.get("name")
            qty_str = row.get("Quantity") or row.get("quantity") or "1"
            set_code = row.get("Set") or row.get("set")
            scryfall_id = row.get("Scryfall ID") or row.get("scryfall_id")

            try:
                quantity = int(qty_str)
            except ValueError:
                quantity = 1

            card_id = None

            if scryfall_id and scryfall_id.lower() in scryfall_map:
                card_id = scryfall_map[scryfall_id.lower()]

            if not card_id and name and set_code:
                key = (name.strip().lower(), set_code.strip().lower())
                card_id = name_set_map.get(key)

            if not card_id and name:
                card_id = name_map.get(name.strip().lower())

            if card_id:
                matched_cards += 1
                unique_set.add(card_id)
                if card_id in collected_quantities:
                    duplicates += 1
                    collected_quantities[card_id] += quantity
                else:
                    collected_quantities[card_id] = quantity
            else:
                unmatched_cards += 1

        print(f"[*] Processed {imported_rows} CSV rows. Performing bulk upsert...")
        print(f"[*] Clearing existing collection for user {user_id} (true source-of-truth replacement)...")
        await session.execute(delete(UserCollection).where(UserCollection.user_id == user_id))

        for card_id, total_qty in collected_quantities.items():
            stmt = insert(UserCollection).values(
                user_id=user_id,
                card_id=card_id,
                quantity=total_qty
            ).on_conflict_do_update(
                index_elements=['user_id', 'card_id'],
                set_={"quantity": total_qty}
            )
            await session.execute(stmt)
        await session.commit()
        print("[+] Collection import successfully committed.")

    return {
        "status": "success",
        "cards_imported": sum(collected_quantities.values()),
        "unique_cards": len(unique_set),
        "matched_cards": matched_cards,
        "unmatched_cards": unmatched_cards,
        "duplicates": duplicates
    }


@router.get("")
async def get_collection(user_id: UUID = Depends(get_current_user_id)):
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Card.name, UserCollection.quantity, Card.types)
            .join(Card, UserCollection.card_id == Card.id)
            .where(UserCollection.user_id == user_id)
        )
        items = res.all()
        return [{"name": item[0], "quantity": item[1], "types": item[2]} for item in items]

@router.get("/stats")
async def get_collection_stats(user_id: UUID = Depends(get_current_user_id)):
    async with AsyncSessionLocal() as session:
        # Total owned cards & unique cards
        totals_res = await session.execute(
            select(
                func.sum(UserCollection.quantity),
                func.count(UserCollection.card_id)
            ).where(UserCollection.user_id == user_id)
        )
        total_qty, unique_count = totals_res.first()

        # Wildcards inventory
        wc_res = await session.execute(select(WildcardInventory).where(WildcardInventory.user_id == user_id))
        wc = wc_res.scalars().first()

        wildcards = {"rare": wc.rare if wc else 0, "mythic": wc.mythic if wc else 0}

        # Count rares and mythics owned using CardPrint rarity or card attributes
        rarity_res = await session.execute(
            select(CardPrint.rarity, func.sum(UserCollection.quantity))
            .join(UserCollection, CardPrint.card_id == UserCollection.card_id)
            .where(UserCollection.user_id == user_id)
            .group_by(CardPrint.rarity)
        )
        rarities = {r[0]: r[1] for r in rarity_res.all()}

        return {
            "total_cards": total_qty or 0,
            "unique_cards": unique_count or 0,
            "rares": rarities.get("rare", 0),
            "mythics": rarities.get("mythic", 0),
            "wildcards": wildcards
        }
