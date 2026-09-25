import sqlite3
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Arena Helper API",
    version="1.2.0",
    description="Engine-centric TCG decision intelligence platform with telemetry and health monitoring."
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
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# Rebuild telemetry table cleanly to ensure engine_id foreign key schema
def init_db():
    conn = get_db()
    # Drop old deck_slug telemetry table if it exists to cleanly migrate to foreign key model
    conn.execute("DROP TABLE IF EXISTS telemetry;")
    conn.execute("""
        CREATE TABLE telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engine_id INTEGER NOT NULL,
            result TEXT NOT NULL,
            turns INTEGER,
            opponent_archetype TEXT,
            timestamp TEXT,
            FOREIGN KEY(engine_id) REFERENCES engines(id)
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

@app.get("/api/health")
def health_check():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM engines")
        engine_count = cursor.fetchone()[0]
        conn.close()
        return {
            "status": "healthy",
            "database": "connected",
            "engines_loaded": engine_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

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
    engine = conn.execute("SELECT id FROM engines WHERE slug = ?", (payload.deck_slug.lower(),)).fetchone()
    if not engine:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Engine slug '{payload.deck_slug}' not found.")

    engine_id = engine["id"]
    ts = payload.timestamp or datetime.utcnow().isoformat() + "Z"

    conn.execute(
        "INSERT INTO telemetry (engine_id, result, turns, opponent_archetype, timestamp) VALUES (?, ?, ?, ?, ?)",
        (engine_id, payload.result.lower(), payload.turns, payload.opponent_archetype.lower(), ts)
    )
    conn.commit()
    
    count = conn.execute("SELECT COUNT(*) as cnt FROM telemetry WHERE engine_id = ?", (engine_id,)).fetchone()["cnt"]
    conn.close()

    return {
        "status": "accepted",
        "matches_recorded": count
    }

@app.get("/api/telemetry/recent")
def get_recent_telemetry(limit: int = 10):
    conn = get_db()
    query = """
        SELECT t.id, e.slug as deck_slug, t.result, t.turns, t.opponent_archetype, t.timestamp
        FROM telemetry t
        JOIN engines e ON t.engine_id = e.id
        ORDER BY t.id DESC
        LIMIT ?
    """
    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "deck_slug": r["deck_slug"],
            "result": r["result"],
            "turns": r["turns"],
            "opponent_archetype": r["opponent_archetype"],
            "timestamp": r["timestamp"]
        }
        for r in rows
    ]

@app.get("/api/stats/{deck_slug}")
def get_deck_stats(deck_slug: str):
    conn = get_db()
    engine = conn.execute("SELECT id, name FROM engines WHERE slug = ?", (deck_slug.lower(),)).fetchone()
    if not engine:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Engine slug '{deck_slug}' not found.")

    rows = conn.execute("SELECT result FROM telemetry WHERE engine_id = ?", (engine["id"],)).fetchall()
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
        WHERE engine_id = ? 
        GROUP BY opponent_archetype
    """
    rows = conn.execute(query, (engine["id"],)).fetchall()
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

    matchups.sort(key=lambda x: x["win_rate"], reverse=True)

    return {
        "best_matchups": [m for m in matchups if m["win_rate"] >= 0.5],
        "worst_matchups": [m for m in matchups if m["win_rate"] < 0.5]
    }
