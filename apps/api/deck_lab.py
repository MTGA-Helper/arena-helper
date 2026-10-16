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
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, func, select
from sqlalchemy.orm import declarative_base

from apps.api.database import AsyncSessionLocal, engine

# Own declarative base so table creation here can never interfere with the
# main models' metadata lifecycle.
LabBase = declarative_base()


class DeckLabSubmission(LabBase):
    __tablename__ = "deck_lab_submissions"

    id = Integer(primary_key=True, autoincrement=True)
    created_at = DateTime(nullable=False, default=datetime.utcnow)
    consent = Boolean(nullable=False, default=False)
    contact = String(320, nullable=True)
    summary = JSON(nullable=True)
    decks = JSON(nullable=True)
    collection = JSON(nullable=True)
    source = String(64, nullable=False, default="deck-lab-web")


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
