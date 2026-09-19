from fastapi import FastAPI, HTTPException
from services.recommendation_service import fetch_recommendations
from services.unlock_service import fetch_unlocks
from services.upgrade_service import fetch_deck_upgrade
from services.next_action_service import get_next_action

app = FastAPI(
    title="Arena Helper API",
    version="1.0.0",
    description="Collection-aware MTGA deck recommendations, unlock analysis, and upgrade advisor."
)

@app.get("/")
async def root():
    return {"message": "Arena Helper API is online", "status": "active"}

@app.get("/api/recommendations/next-action")
async def next_action():
    result = await get_next_action()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/api/recommendations")
async def recommendations():
    result = await fetch_recommendations()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/api/unlocks")
async def unlocks():
    result = await fetch_unlocks()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/api/upgrade/{deck_name}")
async def upgrade_advice(deck_name: str):
    result = await fetch_deck_upgrade(deck_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result