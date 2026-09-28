# fix_evidence_schema.py
import sqlite3

conn = sqlite3.connect("engine_graph.db")
cursor = conn.cursor()

# Drop legacy tables to recreate with full evidence telemetry columns
cursor.execute("DROP TABLE IF EXISTS decision_outcomes;")
cursor.execute("DROP TABLE IF EXISTS engines;")

cursor.execute("""
CREATE TABLE engines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'Operational',
    completion_percentage REAL DEFAULT 100.0,
    missing_role TEXT DEFAULT 'None',
    connection_score INTEGER,
    resilience_score INTEGER,
    must_protect TEXT,
    personal_sample_size INTEGER DEFAULT 0,
    personal_win_rate REAL DEFAULT 0.0,
    community_sample_size INTEGER DEFAULT 0,
    community_win_rate REAL DEFAULT 0.0
);
""")

cursor.execute("""
CREATE TABLE decision_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engine_id INTEGER,
    recommendation_type TEXT,
    engine_gain_per_wildcard REAL,
    wildcard_cost INTEGER,
    confidence_score REAL,
    rationale TEXT,
    FOREIGN KEY(engine_id) REFERENCES engines(id)
);
""")

# Seed with fully populated relational evidence records
engines_data = [
    {
        "slug": "orzhov-drain",
        "name": "Orzhov Drain",
        "desc": "Life gain and drain loop",
        "status": "Ready to Play",
        "completion": 100.0,
        "missing": "None",
        "conn": 9,
        "res": 9,
        "protect": "Bloodletter of Aclazotz",
        "p_samples": 42,
        "p_win": 0.62,
        "c_samples": 3100,
        "c_win": 0.53,
        "rec": "PLAY_NOW",
        "egpw": 0.0,
        "cost": 0,
        "conf": 0.98,
        "rationale": "Engine is fully assembled and ready to pilot."
    },
    {
        "slug": "landfall-hydra",
        "name": "Landfall Growth",
        "desc": "Land-based growth loop",
        "status": "Operational",
        "completion": 85.7,
        "missing": "Amplifier",
        "conn": 10,
        "res": 6,
        "protect": "Mossborn Hydra",
        "p_samples": 84,
        "p_win": 0.58,
        "c_samples": 4215,
        "c_win": 0.54,
        "rec": "SAVE_WILDCARDS",
        "egpw": 0.15,
        "cost": 1,
        "conf": 0.94,
        "rationale": "Current solution performs above community baseline."
    }
]

for e in engines_data:
    cursor.execute("""
    INSERT INTO engines (
        slug, name, description, status, completion_percentage, missing_role,
        connection_score, resilience_score, must_protect,
        personal_sample_size, personal_win_rate, community_sample_size, community_win_rate
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        e["slug"], e["name"], e["desc"], e["status"], e["completion"], e["missing"],
        e["conn"], e["res"], e["protect"],
        e["p_samples"], e["p_win"], e["c_samples"], e["c_win"]
    ))
    
    cursor.execute("SELECT id FROM engines WHERE slug = ?", (e["slug"],))
    eng_id = cursor.fetchone()[0]
    
    cursor.execute("""
    INSERT INTO decision_outcomes (engine_id, recommendation_type, engine_gain_per_wildcard, wildcard_cost, confidence_score, rationale)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (eng_id, e["rec"], e["egpw"], e["cost"], e["conf"], e["rationale"]))

conn.commit()
conn.close()
print("Database schema successfully updated with relational evidence records!")