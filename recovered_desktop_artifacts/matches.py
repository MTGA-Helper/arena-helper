# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from database import AsyncSessionLocal
from models import MatchHistory, User

router = APIRouter(prefix="/matches", tags=["Matches"])

# Temporary auth dependency placeholder tying to your user base
async def get_current_user() -> User:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).limit(1))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
        return user

class MatchIngestRequest(BaseModel):
    player_id: Optional[str] = None
    opponent_id: Optional[str] = None
    player_name: Optional[str] = None
    opponent_name: Optional[str] = None
    deck_name: Optional[str] = None
    result: str  # Win / Loss
    format: Optional[str] = "standard"
    event_name: Optional[str] = None
    rank: Optional[str] = None
    match_started: Optional[datetime] = None
    match_finished: Optional[datetime] = None
    raw_payload: Optional[Dict[str, Any]] = None

@router.post("/ingest")
async def ingest_match(payload: MatchIngestRequest, current_user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as session:
        match_entry = MatchHistory(
            user_id=current_user.id,
            player_id=payload.player_id,
            opponent_id=payload.opponent_id,
            player_name=payload.player_name,
            opponent_name=payload.opponent_name,
            deck_name=payload.deck_name,
            result=payload.result,
            format=payload.format,
            event_name=payload.event_name,
            rank=payload.rank,
            match_started=payload.match_started,
            match_finished=payload.match_finished,
            raw_payload=payload.raw_payload,
            created_at=datetime.now(timezone.utc)
        )
        session.add(match_entry)
        await session.commit()
    return {"status": "success", "message": "Match telemetry stored securely with raw payload preservation."}

@router.get("/history")
async def get_match_history(current_user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(MatchHistory)
            .where(MatchHistory.user_id == current_user.id)
            .order_by(MatchHistory.created_at.desc())
            .limit(50)
        )
        matches = res.scalars().all()
        return [
            {
                "id": m.id,
                "deck_name": m.deck_name,
                "result": m.result,
                "format": m.format,
                "opponent_name": m.opponent_name,
                "rank": m.rank,
                "created_at": m.created_at
            }
            for m in matches
        ]
