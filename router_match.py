from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from database import AsyncSessionLocal

class MatchIngestRequest(BaseModel):
    user_id: str = Field(..., description="UUID of the authenticated user")
    player_id: str = Field(..., description="MTGA Player ID")
    opponent_id: Optional[str] = Field(None, description="Opponent Player ID if available")
    deck_name: str = Field(..., description="Name or archetype of the deck used")
    result: str = Field(..., description="Match result: Win, Loss, or Draw")
    format: str = Field(..., description="Game format: Standard, Historic, Draft, etc.")
    raw_events: Optional[List[Dict[str, Any]]] = Field(default=[], description="Raw parsed telemetry event payloads")

class MatchResponse(BaseModel):
    id: int
    user_id: str
    deck_name: str
    result: str
    format: str
    timestamp: Optional[str] = None

    class Config:
        from_attributes = True

router = APIRouter(prefix="/matches", tags=["Matches"])

@router.post("/ingest", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def ingest_match(payload: MatchIngestRequest):
    async with AsyncSessionLocal() as session:
        try:
            query = text("""
                INSERT INTO match_histories (user_id, player_id, opponent_id, deck_name, result, format)
                VALUES (:user_id, :player_id, :opponent_id, :deck_name, :result, :format)
                RETURNING id, user_id, deck_name, result, format, timestamp;
            """)
            result = await session.execute(query, {
                "user_id": payload.user_id,
                "player_id": payload.player_id,
                "opponent_id": payload.opponent_id,
                "deck_name": payload.deck_name,
                "result": payload.result,
                "format": payload.format
            })
            await session.commit()
            row = result.fetchone()
            
            return {
                "id": row.id,
                "user_id": row.user_id,
                "deck_name": row.deck_name,
                "result": row.result,
                "format": row.format,
                "timestamp": str(row.timestamp) if row.timestamp else None
            }
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/history", response_model=List[MatchResponse])
async def get_match_history(user_id: str):
    async with AsyncSessionLocal() as session:
        query = text("SELECT id, user_id, deck_name, result, format, timestamp FROM match_histories WHERE user_id = :user_id ORDER BY timestamp DESC;")
        result = await session.execute(query, {"user_id": user_id})
        rows = result.fetchall()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "deck_name": r.deck_name,
                "result": r.result,
                "format": r.format,
                "timestamp": str(r.timestamp) if r.timestamp else None
            } for r in rows
        ]