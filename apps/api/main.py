import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Arena Helper API",
    version="1.0.0",
    description="Engine-centric TCG decision intelligence platform backed by SQLite."
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

    # Query engine record matching actual SQLite schema
    engine = conn.execute("SELECT * FROM engines WHERE slug = ?", (deck_slug.lower(),)).fetchone()
    if not engine:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Engine slug '{deck_slug}' not found in knowledge graph.")

    # Fetch corresponding decision outcome metrics if present
    outcome = conn.execute("SELECT * FROM decision_outcomes WHERE engine_id = ?", (engine["id"],)).fetchone()
    conn.close()

    # Construct relational diagnostics safely matching available database columns
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
