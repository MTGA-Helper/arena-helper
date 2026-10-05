import sqlite3
db = sqlite3.connect('engine_graph.db')
for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(r[0])
