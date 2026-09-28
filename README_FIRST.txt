ARENA HELPER
Decision Intelligence Platform

Current Status
==============
- FastAPI API operational
- SQLite knowledge graph operational
- Collection sync operational
- 5,963 cards imported
- Telemetry parser awaiting Player.log tuning

Run API
=======
uvicorn main:app --reload

Open Swagger
============
http://127.0.0.1:8000/docs

Run Updater
===========
python arena_updater.py

Next Task
=========
Inspect Player.log and update regex patterns in sync_matches()
to populate user_matches with observed telemetry.
