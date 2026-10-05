import os
lines = [l.strip() for l in open('.env') if l.strip() and not l.startswith('#') and '=' in l]
env = dict(l.split('=', 1) for l in lines)
url = env.get('SYNC_DATABASE_URL') or env.get('DATABASE_URL')
import psycopg2
conn = psycopg2.connect(url)
cur = conn.cursor()
for t in ['cards', 'card_prints', 'meta_card_stats']:
    try:
        cur.execute('SELECT COUNT(*) FROM ' + t)
        print(t, cur.fetchone()[0])
    except Exception:
        conn.rollback()
        print(t, 'missing or error')
conn.close()
