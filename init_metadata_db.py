# init_metadata_db.py
import sqlite3

conn = sqlite3.connect("engine_graph.db")
cursor = conn.cursor()

# Drop and recreate engines with metadata columns
cursor.execute("DROP TABLE IF EXISTS decision_outcomes;")
cursor.execute("DROP TABLE IF EXISTS engines;")

cursor.execute("""
CREATE TABLE engines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE,
    name TEXT,
    description TEXT,
    status TEXT,
    connection_score INTEGER,
    resilience_score INTEGER,
    must_protect TEXT
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

# Seed with full V2 metadata
engines_data = [
    {
        "slug": "orzhov-drain",
        "name": "Orzhov Drain",
        "desc": "Life gain and drain loop",
        "status": "Ready to Play",
        "conn": 9,
        "res": 9,
        "protect": "Bloodletter of Aclazotz",
        "rec": "PLAY_NOW",
        "egpw": 0.0,
        "cost": 0,
        "conf": 0.98,
        "rationale": "Engine is fully assembled and ready to pilot!"
    },
    {
        "slug": "landfall-growth",
        "name": "Landfall Growth",
        "desc": "Land-based growth loop",
        "status": "One Amplifier Away",
        "conn": 10,
        "res": 6,
        "protect": "Mossborn Hydra",
        "rec": "SAVE_WILDCARDS",
        "egpw": 0.15,
        "cost": 1,
        "conf": 0.94,
        "rationale": "Current solution (Felidar Retreat) performs above community baseline."
    }
]

for e in engines_data:
    cursor.execute("""
    INSERT INTO engines (slug, name, description, status, connection_score, resilience_score, must_protect)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (e["slug"], e["name"], e["desc"], e["status"], e["conn"], e["res"], e["protect"]))
    
    cursor.execute("SELECT id FROM engines WHERE slug = ?", (e["slug"],))
    eng_id = cursor.fetchone()[0]
    
    cursor.execute("""
    INSERT INTO decision_outcomes (engine_id, recommendation_type, engine_gain_per_wildcard, wildcard_cost, confidence_score, rationale)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (eng_id, e["rec"], e["egpw"], e["cost"], e["conf"], e["rationale"]))

conn.commit()
conn.close()
print("Engine metadata successfully seeded into SQLite!")