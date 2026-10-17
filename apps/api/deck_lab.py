# -*- coding: utf-8 -*-
"""
Deck Lab — pre-alpha tester surface for Arena Helper.

Serves the Deck Lab page at /deck-lab and a small submissions API backed by
the production database (Neon in production, SQLite fallback locally):

  GET  /deck-lab                        -> the Lab page (static HTML)
  POST /api/deck-lab/submissions        -> consent-gated tester data intake
  GET  /api/deck-lab/submissions/count  -> public count of stored submissions
  GET  /api/deck-lab/submissions        -> admin read; requires the
                                           X-Lab-Admin-Token header to match
                                           the LAB_ADMIN_TOKEN env var

Design notes:
- The table is created lazily with checkfirst=True (same create-if-missing
  idiom main.py already uses for the telemetry table), so this module needs
  no migration and touches no existing tables.
- Consent is enforced server-side: a submission without consent=true is
  rejected, no matter what the client does.
- Analysis (completion / wildcard math) happens in the browser; this API
  only stores what a tester deliberately shares.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, func, select
from sqlalchemy.orm import declarative_base

from apps.api.database import AsyncSessionLocal, engine

# Own declarative base so table creation here can never interfere with the
# main models' metadata lifecycle.
LabBase = declarative_base()


class DeckLabSubmission(LabBase):
    __tablename__ = "deck_lab_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    consent = Column(Boolean, nullable=False, default=False)
    contact = Column(String(320), nullable=True)
    summary = Column(JSON, nullable=True)
    decks = Column(JSON, nullable=True)
    collection = Column(JSON, nullable=True)
    source = Column(String(64), nullable=False, default="deck-lab-web")


router = APIRouter(tags=["Deck Lab"])

_table_ready = False


async def _ensure_table() -> None:
    global _table_ready
    if _table_ready:
        return
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: DeckLabSubmission.__table__.create(
                sync_conn, checkfirst=True
            )
        )
    _table_ready = True


class SubmissionIn(BaseModel):
    consent: bool
    contact: Optional[str] = None
    summary: Optional[dict[str, Any]] = None
    decks: Optional[list[Any]] = None
    collection: Optional[dict[str, Any]] = None
    source: Optional[str] = "deck-lab-web"


@router.get("/deck-lab", response_class=HTMLResponse)
async def deck_lab_page() -> HTMLResponse:
    html_path = Path(__file__).parent / "deck_lab.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


FORMAT_COLUMNS = {"standard", "alchemy", "explorer", "historic", "timeless", "brawl"}


def analyze_deck_data(fmt: str, mainboard, sideboard, card_index: dict) -> dict:
    """Pure deck analysis: legality, Arena translation, and breakdowns.

    card_index maps lowercased card name -> {
        name, colors, color_identity, types, mana_cost, mana_value,
        cheapest_rarity, sets, legalities {format: bool}, tags [str]
    } built by the DB layer. Kept pure so the math is testable without a DB.
    """
    rank = {"common": 0, "uncommon": 1, "rare": 2, "mythic": 3}
    violations = []
    main_count = sum(q for q, _ in mainboard)
    side_count = sum(q for q, _ in sideboard)
    if main_count < 60:
        violations.append({"type": "mainboard_size", "detail": f"Mainboard has {main_count} cards; {fmt} requires at least 60."})
    if side_count > 15:
        violations.append({"type": "sideboard_size", "detail": f"Sideboard has {side_count} cards; maximum is 15."})

    copies: dict[str, int] = {}
    for qty, name in list(mainboard) + list(sideboard):
        copies[name.strip().lower()] = copies.get(name.strip().lower(), 0) + qty

    cards_out = []
    color_cards = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
    pips = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
    type_counts: dict[str, int] = {}
    curve: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    seen = set()
    for qty, name in list(mainboard) + list(sideboard):
        key = name.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        info = card_index.get(key)
        in_main = sum(q for q, n in mainboard if n.strip().lower() == key)
        if info is None:
            violations.append({"type": "unknown_card", "card": name, "detail": f"{name} is not in the card database."})
            cards_out.append({"name": name, "on_arena": False, "cheapest_rarity": None, "sets": [], "legal_in_format": False})
            continue
        types = [str(t) for t in (info.get("types") or [])]
        is_basic = any("basic" in t.lower() for t in types)
        if copies.get(key, 0) > 4 and not is_basic:
            violations.append({"type": "copy_limit", "card": info["name"], "detail": f"{copies[key]} copies of {info['name']}; maximum is 4 (mainboard + sideboard)."})
        legal = bool((info.get("legalities") or {}).get(fmt, False))
        if not legal:
            violations.append({"type": "not_legal_in_format", "card": info["name"], "detail": f"{info['name']} is not legal in {fmt}."})
        cards_out.append({
            "name": info["name"],
            "on_arena": bool(info.get("sets")),
            "cheapest_rarity": info.get("cheapest_rarity"),
            "sets": info.get("sets") or [],
            "legal_in_format": legal,
        })
        if in_main:
            for c in info.get("color_identity") or []:
                if c in color_cards:
                    color_cards[c] += in_main
            for ch in (info.get("mana_cost") or ""):
                if ch in pips:
                    pips[ch] += in_main
            is_land = any("land" in t.lower() for t in types)
            for t in types:
                tl = t.lower()
                for bucket in ("creature", "instant", "sorcery", "artifact", "enchantment", "planeswalker", "land", "battle"):
                    if bucket in tl:
                        type_counts[bucket] = type_counts.get(bucket, 0) + in_main
            if not is_land:
                mv = int(info.get("mana_value") or 0)
                bucket = str(min(mv, 7))
                curve[bucket] = curve.get(bucket, 0) + in_main
            for tag in info.get("tags") or []:
                tag_counts[tag] = tag_counts.get(tag, 0) + in_main

    themes = [t for t, _ in sorted(tag_counts.items(), key=lambda kv: -kv[1])[:6]]
    return {
        "format": fmt,
        "mainboard_count": main_count,
        "sideboard_count": side_count,
        "legality": {"legal": not violations, "violations": violations},
        "cards": cards_out,
        "breakdown": {
            "colors_by_identity": color_cards,
            "mana_pips": pips,
            "types": type_counts,
            "mana_curve_nonland": curve,
            "themes": themes,
        },
    }


class AnalyzeRequest(BaseModel):
    format: str = "standard"
    mainboard: list[Any]
    sideboard: list[Any] = []


@router.post("/api/deck-lab/analyze-deck")
async def analyze_deck(body: AnalyzeRequest):
    fmt = body.format.strip().lower()
    if fmt not in FORMAT_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{body.format}'. Supported: {sorted(FORMAT_COLUMNS)}.")
    from apps.api.models import Card, CardLegality, CardPrint, CardTag

    def norm_rows(rows):
        out = []
        for qty, name in rows:
            out.append((int(qty), str(name)))
        return out

    mainboard = norm_rows(body.mainboard)
    sideboard = norm_rows(body.sideboard)
    names = {n.strip().lower() for _, n in mainboard + sideboard}
    rank = {"common": 0, "uncommon": 1, "rare": 2, "mythic": 3}
    card_index: dict = {}
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                Card.name, Card.colors, Card.color_identity, Card.types,
                Card.mana_cost, Card.mana_value,
                CardPrint.rarity, CardPrint.set_code,
                CardLegality.standard, CardLegality.alchemy, CardLegality.explorer,
                CardLegality.historic, CardLegality.timeless, CardLegality.brawl,
                CardTag.tag,
            )
            .join(CardPrint, CardPrint.card_id == Card.id, isouter=True)
            .join(CardLegality, CardLegality.card_id == Card.id, isouter=True)
            .join(CardTag, CardTag.card_id == Card.id, isouter=True)
        )
        for row in result.all():
            key = row[0].strip().lower()
            if key not in names:
                continue
            entry = card_index.setdefault(key, {
                "name": row[0], "colors": row[1] or [], "color_identity": row[2] or [],
                "types": row[3] or [], "mana_cost": row[4] or "", "mana_value": row[5] or 0,
                "cheapest_rarity": None, "sets": [], "tags": [],
                "legalities": {"standard": bool(row[8]), "alchemy": bool(row[9]),
                               "explorer": bool(row[10]), "historic": bool(row[11]),
                               "timeless": bool(row[12]), "brawl": bool(row[13])},
            })
            rarity = (row[6] or "").strip().lower()
            if rarity in rank and (entry["cheapest_rarity"] is None or rank[rarity] < rank[entry["cheapest_rarity"]]):
                entry["cheapest_rarity"] = rarity
            if row[7] and row[7] not in entry["sets"]:
                entry["sets"].append(row[7])
            if row[14] and row[14] not in entry["tags"]:
                entry["tags"].append(row[14])
    return analyze_deck_data(fmt, mainboard, sideboard, card_index)


@router.get("/api/deck-lab/winners")
async def winners_library():
    """Dated library of recent tournament-winning decklists (file-backed)."""
    lib_path = Path(__file__).parent / "winners_library_standard.json"
    if not lib_path.exists():
        return {"compiled_date": None, "format": None, "decks": []}
    return json.loads(lib_path.read_text(encoding="utf-8"))


class RarityRequest(BaseModel):
    names: list[str]


@router.post("/api/deck-lab/rarities")
async def rarities(body: RarityRequest):
    """Card rarities from the production card database (Neon).

    For each requested card name, returns the CHEAPEST Arena printing's
    rarity across card_prints — if any printing of a card exists at a lower
    rarity, Arena lets you build with that printing, so the wildcard cost
    uses the lowest. Unknown names are omitted; the client falls back to
    Scryfall, then 'unknown'.
    """
    from apps.api.models import Card, CardPrint

    rank = {"common": 0, "uncommon": 1, "rare": 2, "mythic": 3}
    wanted = {n.strip().lower() for n in body.names if n and n.strip()}
    if not wanted:
        return {"rarities": {}}
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Card.name, CardPrint.rarity)
            .join(CardPrint, CardPrint.card_id == Card.id)
        )
        best: dict[str, str] = {}
        for name, rarity in result.all():
            key = name.strip().lower()
            if key not in wanted or rarity is None:
                continue
            r = rarity.strip().lower()
            if r not in rank:
                continue
            if key not in best or rank[r] < rank[best[key]]:
                best[key] = r
        return {"rarities": best}


@router.get("/api/deck-lab/meta-decks")
async def meta_decks():
    """The dated meta library snapshot shipped with the service.

    Data lives in meta_library_standard.json next to this module so a meta
    refresh is a file swap, not a schema change. Each deck carries its
    source and the snapshot date; the client does collection math locally.
    """
    lib_path = Path(__file__).parent / "meta_library_standard.json"
    if not lib_path.exists():
        return {"snapshot_date": None, "format": None, "decks": []}
    return json.loads(lib_path.read_text(encoding="utf-8"))


@router.post("/api/deck-lab/submissions")
async def create_submission(body: SubmissionIn):
    if not body.consent:
        raise HTTPException(
            status_code=400,
            detail="Consent is required: submissions are only accepted with consent=true.",
        )
    await _ensure_table()
    async with AsyncSessionLocal() as session:
        row = DeckLabSubmission(
            consent=True,
            contact=body.contact,
            summary=body.summary,
            decks=body.decks,
            collection=body.collection,
            source=body.source or "deck-lab-web",
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return {
            "id": row.id,
            "received_at": row.created_at.isoformat() + "Z",
            "status": "stored",
        }


@router.get("/api/deck-lab/submissions/count")
async def submissions_count():
    await _ensure_table()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count(DeckLabSubmission.id)))
        return {"count": result.scalar_one()}


@router.get("/api/deck-lab/submissions")
async def list_submissions(
    include_payload: bool = False,
    x_lab_admin_token: Optional[str] = Header(default=None),
):
    expected = os.environ.get("LAB_ADMIN_TOKEN")
    if not expected or x_lab_admin_token != expected:
        raise HTTPException(
            status_code=403,
            detail="Admin token required (set LAB_ADMIN_TOKEN and send X-Lab-Admin-Token).",
        )
    await _ensure_table()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DeckLabSubmission).order_by(DeckLabSubmission.id.desc()).limit(100)
        )
        rows = result.scalars().all()
        out = []
        for r in rows:
            item = {
                "id": r.id,
                "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
                "contact": r.contact,
                "summary": r.summary,
                "source": r.source,
            }
            if include_payload:
                item["decks"] = r.decks
                item["collection"] = r.collection
            out.append(item)
        return {"submissions": out}
