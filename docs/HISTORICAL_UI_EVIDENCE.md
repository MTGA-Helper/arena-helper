# Historical UI Evidence & Workflow Catalog

Cataloging Tier 3 visual memory, Swagger outputs, and prior test sessions to ensure our reassembled backend powers expected user workflows.

## Catalog Entries

### 1. Collection Import & Inventory Dashboard
* **Observed Actions:** Uploading .csv file exports from MTG Arena, reviewing unique card counts, tracking rare/mythic ownership totals, and monitoring wildcard inventories.
* **Backend Wiring:** Directly mapped to pps/api/collection.py (POST /collection/upload, GET /collection, GET /collection/stats).
* **Evidence Level:** Code Verified + Visual Memory.

### 2. Deck Recommendation & Craft Advisor View
* **Observed Actions:** Browsing meta-analyzed deck lists sorted by match percentage, evaluating missing card deficits, and viewing optimized wildcard crafting priority reports.
* **Backend Wiring:** Powered by pps/api/recommend_engine.py and pps/api/craft_priority.py.
* **Evidence Level:** Code Verified + Visual Memory.

### 3. Upgrade Advisor & Match History
* **Observed Actions:** Inspecting individual deck buildability, tracking win/loss match telemetry, and reviewing opponent/format stats.
* **Backend Wiring:** Powered by pps/api/upgrade_advisor.py and pps/api/matches.py.
* **Evidence Level:** Code Verified + Render API Endpoints.
