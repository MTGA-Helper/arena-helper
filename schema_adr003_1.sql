-- ADR-003.1: The Evidence Hierarchy & Empirical Upgrade Outcomes

CREATE TABLE IF NOT EXISTS evidence_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT UNIQUE,
    hierarchy_level INTEGER,
    base_trust_weight REAL
);

CREATE TABLE IF NOT EXISTS empirical_upgrade_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engine_id INTEGER,
    role_family_id INTEGER,
    card_id INTEGER,
    sample_size INTEGER,
    avg_win_rate_delta REAL,
    avg_efficiency_delta REAL,
    measured_egpw REAL
);

CREATE TABLE IF NOT EXISTS evidence_graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_card_id INTEGER,
    target_card_id INTEGER,
    evidence_source_id INTEGER,
    observed_frequency INTEGER,
    confidence_score REAL
);
