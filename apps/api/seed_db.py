# seed_db.py
import sqlite3

conn = sqlite3.connect("engine_graph.db")
cursor = conn.cursor()

# 1. Ensure the core tables exist
cursor.executescript("""
CREATE TABLE IF NOT EXISTS engines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS decision_outcomes (
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

# 2. Insert test engines so endpoints return real data
test_engines = [
    ("Orzhov Drain", "Life gain and drain loop", "PLAY_NOW", 0.0, 0, 0.98, "Engine is fully assembled and ready to pilot!"),
    ("Landfall Growth", "Land-based growth loop", "SAVE_WILDCARDS", 0.15, 1, 0.94, "Current solution (Felidar Retreat) performs above community baseline.")
]

for name, desc, rec_type, egpw, cost, conf, rationale in test_engines:
    cursor.execute("INSERT OR IGNORE INTO engines (name, description) VALUES (?, ?)", (name, desc))
    cursor.execute("SELECT id FROM engines WHERE name = ?", (name,))
    eng_id = cursor.fetchone()[0]
    
    cursor.execute("""
    INSERT OR REPLACE INTO decision_outcomes 
    (engine_id, recommendation_type, engine_gain_per_wildcard, wildcard_cost, confidence_score, rationale)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (eng_id, rec_type, egpw, cost, conf, rationale))

conn.commit()
conn.close()
print("Successfully seeded engines and decision outcomes into engine_graph.db!")