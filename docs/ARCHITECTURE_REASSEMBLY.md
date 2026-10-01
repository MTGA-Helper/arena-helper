# Architecture Reassembly Flow — Arena Helper

The unified request and data pipeline for the reassembled Arena Helper platform:

[ User Portal Interface ]
           ↓
    [ Authentication ] (JWT Bearer Token validation via user-portal/auth.py)
           ↓
      [ User Model ] (PostgreSQL / SQLite User & Wildcard State)
           ↓
[ Collection Upload ] (CSV parsing & Scryfall/Set ID resolution)
           ↓
  [ UserCollection ] (Persistent ownership mapping)
           ↓
[ Collection Analytics ] (Ownership stats & rarity tracking)
           ↓
  [ Deck Analysis ] (Evaluating Meta, Synergy, Consistency, Curve)
           ↓
 [ Upgrade Advisor ] (Checking buildability against current collection)
           ↓
   [ Craft Advisor ] (Optimizing rare/mythic wildcard acquisition ROI)
           ↓
[ Recommendation Engine ] (Scoring personalized deck completion matches)
           ↓
[ Match Telemetry Feedback Loop ] (Ingesting match results to refine meta analytics)
           ↓
[ Improved Recommendations ]
