import sqlite3
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Arena Helper API",
    version="1.1.0",
    description="Engine-centric TCG decision intelligence platform with telemetry."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect("engine_graph.db")
    conn.row_factory = sqlite3.Row
    return conn

# Initialize Telemetry table if it doesn't exist
def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_slug TEXT NOT NULL,
            result TEXT NOT NULL,
            turns INTEGER,
            opponent_archetype TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

class TelemetryPayload(BaseModel):
    deck_slug: str
    result: str  # "win" or "loss"
    turns: Optional[int] = 8
    opponent_archetype: Optional[str] = "unknown"
    timestamp: Optional[str] = None

@app.get("/api/engines")
def list_engines():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT slug FROM engines")
    rows = cursor.fetchall()
    conn.close()
    return [row["slug"] for row in rows]

@app.get("/api/upgrade/{deck_slug}")
def get_upgrade_advice(deck_slug: str):
    conn = get_db()
    engine = conn.execute("SELECT * FROM engines WHERE slug = ?", (deck_slug.lower(),)).fetchone()
    if not engine:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Engine slug '{deck_slug}' not found in knowledge graph.")

    outcome = conn.execute("SELECT * FROM decision_outcomes WHERE engine_id = ?", (engine["id"],)).fetchone()
    conn.close()

    diagnostics = {
        "evidence_version": "ADR-003.1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": "SQLite Knowledge Graph",
        "decision_record_id": outcome["id"] if outcome else None,
        "engine_state": engine["status"],
        "connection_score": engine["connection_score"],
        "resilience_score": engine["resilience_score"],
        "must_protect": engine["must_protect"]
    }

    return {
        "engine": engine["name"],
        "slug": engine["slug"],
        "status": engine["status"],
        "decision": outcome["recommendation_type"] if outcome else "PLAY_NOW",
        "expected_egpw": outcome["engine_gain_per_wildcard"] if outcome else 0.0,
        "wildcard_cost": outcome["wildcard_cost"] if outcome else 0,
        "confidence": outcome["confidence_score"] if outcome else 0.90,
        "rationale": outcome["rationale"] if outcome else "Baseline operational.",
        "diagnostics": diagnostics
    }

@app.post("/api/telemetry")
def ingest_telemetry(payload: TelemetryPayload):
    conn = get_db()
    # Verify engine exists
    engine = conn.execute("SELECT id FROM engines WHERE slug = ?", (payload.deck_slug.lower(),)).fetchone()
    if not engine:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Engine slug '{payload.deck_slug}' not found.")

    ts = payload.timestamp or datetime.utcnow().isoformat() + "Z"
    conn.execute(
        "INSERT INTO telemetry (deck_slug, result, turns, opponent_archetype, timestamp) VALUES (?, ?, ?, ?, ?)",
        (payload.deck_slug.lower(), payload.result.lower(), payload.turns, payload.opponent_archetype.lower(), ts)
    )
    conn.commit()
    
    # Count total matches recorded for this deck
    count = conn.execute("SELECT COUNT(*) as cnt FROM telemetry WHERE deck_slug = ?", (payload.deck_slug.lower(),)).fetchone()["cnt"]
    conn.close()

    return {
        "status": "accepted",
        "matches_recorded": count
    }

@app.get("/api/stats/{deck_slug}")
def get_deck_stats(deck_slug: str):
    conn = get_db()
    engine = conn.execute("SELECT name FROM engines WHERE slug = ?", (deck_slug.lower(),)).fetchone()
    if not engine:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Engine slug '{deck_slug}' not found.")

    rows = conn.execute("SELECT result FROM telemetry WHERE deck_slug = ?", (deck_slug.lower(),)).fetchall()
    conn.close()

    matches = len(rows)
    wins = sum(1 for r in rows if r["result"] == "win")
    losses = matches - wins
    win_rate = round(wins / matches, 3) if matches > 0 else 0.0

    return {
        "deck": engine["name"],
        "matches": matches,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate
    }

@app.get("/api/matchups/{deck_slug}")
def get_deck_matchups(deck_slug: str):
    conn = get_db()
    engine = conn.execute("SELECT id FROM engines WHERE slug = ?", (deck_slug.lower(),)).fetchone()
    if not engine:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Engine slug '{deck_slug}' not found.")

    query = """
        SELECT opponent_archetype, 
               COUNT(*) as total, 
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins 
        FROM telemetry 
        WHERE deck_slug = ? 
        GROUP BY opponent_archetype
    """
    rows = conn.execute(query, (deck_slug.lower(),)).fetchall()
    conn.close()

    matchups = []
    for r in rows:
        total = r["total"]
        wins = r["wins"]
        wr = round(wins / total, 3) if total > 0 else 0.0
        matchups.append({
            "opponent_archetype": r["opponent_archetype"],
            "matches": total,
            "win_rate": wr
        })

    # Sort best to worst matchups
    matchups.sort(key=lambda x: x["win_rate"], reverse=True)

    return {
        "best_matchups": [m for m in matchups if m["win_rate"] >= 0.5],
        "worst_matchups": [m for m in matchups if m["win_rate"] < 0.5]
    }
