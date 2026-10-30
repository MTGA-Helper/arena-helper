// Arena Helper — HTML dashboard generator (added Oct 30, 2026)
// Queries the local ELK stack for all season *_94 match docs and renders ONE
// self-contained HTML page (inline CSS, no external assets) next to this script.
// ES credentials are read from the worktree .env at RUNTIME only; nothing
// secret is ever written into the generated HTML.
import fs from 'node:fs';
import https from 'node:https';
import path from 'node:path';

const here = import.meta.dirname;
const worktreeRoot = path.join(here, '..', '..');

// --- read .env at runtime (values never printed, never embedded in output) ---
const env = {};
const envPath = path.join(worktreeRoot, '.env');
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}
const ES_URL = process.env.ELASTICSEARCH_URL ?? env.ELASTICSEARCH_URL ?? 'https://127.0.0.1:9200';
const ES_USER = env.ELASTIC_USERNAME ?? 'elastic';
const ES_PASS = env.ELASTIC_PASSWORD ?? '';
if (!ES_PASS) throw new Error('ELASTIC_PASSWORD not found in worktree .env');
const caPath = path.join(here, '..', 'certs-ca.crt');
const ca = fs.existsSync(caPath) ? fs.readFileSync(caPath) : undefined;

function esSearch(body) {
  return new Promise((resolve, reject) => {
    const url = new URL('/*_94/_search', ES_URL);
    const req = https.request(
      url,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Basic ' + Buffer.from(`${ES_USER}:${ES_PASS}`).toString('base64'),
        },
        ca,
        rejectUnauthorized: ca ? true : false,
      },
      (res) => {
        let data = '';
        res.on('data', (c) => (data += c));
        res.on('end', () => {
          if (res.statusCode >= 300) reject(new Error(`ES ${res.statusCode}: ${data.slice(0, 300)}`));
          else resolve(JSON.parse(data));
        });
      },
    );
    req.on('error', reject);
    req.end(JSON.stringify(body));
  });
}

// rankScore — same scheme documented in the Kibana dashboard's legend panel:
// class base (Bronze 0, Silver 24, Gold 48, Platinum 72, Diamond 96, Mythic 120)
// + (4 - level) * 6 + step.
const CLASS_BASE = { Bronze: 0, Silver: 24, Gold: 48, Platinum: 72, Diamond: 96, Mythic: 120 };
function rankScore(d) {
  const base = CLASS_BASE[d.constructedClass];
  if (base === undefined || d.constructedLevel == null) return null;
  if (d.constructedClass === 'Mythic') return 120;
  return base + (4 - d.constructedLevel) * 6 + (d.constructedStep ?? 0);
}

const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const res = await esSearch({
  size: 1000,
  sort: [{ timestamp: { order: 'asc' } }],
  _source: { excludes: ['playedCards'] },
  query: { match_all: {} },
});
const docs = res.hits.hits.map((h) => ({ _index: h._index, ...h._source }));
if (!docs.length) throw new Error('No docs in *_94 indices — nothing to render.');

const isWin = (d) => d.result === 'Win';
const pct = (w, n) => (n ? `${((w / n) * 100).toFixed(1)}%` : '—');
function tally(list) {
  const w = list.filter(isWin).length;
  return { n: list.length, w, l: list.length - w, pct: pct(w, list.length) };
}

const overall = tally(docs);
const latest = docs[docs.length - 1];
const latestScore = rankScore(latest);

// by format/event (group on the doc's eventId, fall back to index name)
const byFormat = new Map();
for (const d of docs) {
  const key = d.eventId || d._index;
  if (!byFormat.has(key)) byFormat.set(key, []);
  byFormat.get(key).push(d);
}

// per-deck-by-format (Matt's ask): deck name x event
const deckFormat = new Map(); // deck -> Map(event -> docs)
for (const d of docs) {
  const deck = d.deck || d.myDeck || '(Unknown deck)';
  const fmt = d.eventId || d._index;
  if (!deckFormat.has(deck)) deckFormat.set(deck, new Map());
  const m = deckFormat.get(deck);
  if (!m.has(fmt)) m.set(fmt, []);
  m.get(fmt).push(d);
}

const fmtTime = (ts) =>
  new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Los_Angeles',
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true,
  }).format(new Date(ts));

const formatCards = [...byFormat.entries()]
  .map(([fmt, list]) => {
    const t = tally(list);
    return `<div class="card"><div class="card-label">${esc(fmt)}</div>
      <div class="card-big">${t.pct}</div>
      <div class="card-sub">${t.w}W – ${t.l}L · ${t.n} match${t.n === 1 ? '' : 'es'}</div></div>`;
  })
  .join('\n');

const deckRows = [...deckFormat.entries()]
  .sort((a, b) => a[0].localeCompare(b[0]))
  .map(([deck, m]) => {
    const all = [...m.values()].flat();
    const tot = tally(all);
    const cells = [...m.entries()]
      .map(([fmt, list]) => {
        const t = tally(list);
        return `<tr><td class="deck">${esc(deck)}</td><td>${esc(fmt)}</td><td>${t.n}</td><td>${t.w}–${t.l}</td><td>${t.pct}</td></tr>`;
      })
      .join('\n');
    return cells + `<tr class="subtotal"><td class="deck">${esc(deck)} — all formats</td><td></td><td>${tot.n}</td><td>${tot.w}–${tot.l}</td><td>${tot.pct}</td></tr>`;
  })
  .join('\n');

const matchRows = [...docs]
  .sort((a, b) => b.timestamp - a.timestamp)
  .map(
    (d) => `<tr>
      <td>${esc(fmtTime(d.timestamp))} PT</td>
      <td class="deck">${esc(d.deck || d.myDeck || '')}</td>
      <td>${esc(d.opponent || d.opponentGamerTag || '')}</td>
      <td>${esc(d.eventId || d._index)}</td>
      <td class="${isWin(d) ? 'win' : 'loss'}">${esc(d.result)}</td>
      <td>${esc(d.rankLabel || '—')}</td>
    </tr>`,
  )
  .join('\n');

const indicesSeen = [...new Set(docs.map((d) => d._index))].sort().join(', ');
const generatedAt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Los_Angeles', dateStyle: 'medium', timeStyle: 'short',
}).format(new Date());

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Arena Helper — Dashboard (testing)</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0e1116; color:#e6e9ee; font:15px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  main { max-width: 960px; margin: 0 auto; padding: 28px 20px 48px; }
  h1 { font-size: 26px; margin: 0 0 4px; }
  h2 { font-size: 17px; margin: 30px 0 10px; color:#9fd1ff; }
  .sub { color:#8b94a3; font-size: 13px; }
  .hero { display:flex; flex-wrap:wrap; gap:14px; margin-top:18px; }
  .card { background:#171c24; border:1px solid #262e3a; border-radius:12px; padding:16px 18px; min-width:180px; flex:1; }
  .card-label { color:#8b94a3; font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
  .card-big { font-size:30px; font-weight:700; margin:4px 0 2px; }
  .card-sub { color:#aeb7c4; font-size:13px; }
  table { width:100%; border-collapse:collapse; background:#141922; border:1px solid #262e3a; border-radius:12px; overflow:hidden; }
  th, td { padding:9px 12px; text-align:left; font-size:14px; border-bottom:1px solid #222a36; }
  th { color:#8b94a3; font-size:12px; text-transform:uppercase; letter-spacing:.05em; }
  tr:last-child td { border-bottom:none; }
  td.deck { font-weight:600; }
  tr.subtotal td { background:#1b222d; color:#c9d3e0; }
  .win { color:#57d977; font-weight:700; }
  .loss { color:#ff7a72; font-weight:700; }
  .stub { border:1px dashed #4a4230; background:#1d1a12; border-radius:12px; padding:16px 18px; }
  .stub .tag { display:inline-block; background:#4a4230; color:#ffd479; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:700; letter-spacing:.04em; }
  .stub p { color:#b8b09a; margin:10px 0 0; }
  footer { margin-top:34px; color:#5f6875; font-size:12px; }
</style>
</head>
<body>
<main>
  <h1>Arena Helper — Dashboard</h1>
  <div class="sub">Testing build · player <strong>${esc(latest.myGamerTag || 'owlensteed')}</strong> · MTGA season ${esc(latest.constructedSeasonOrdinal ?? '')} · generated ${esc(generatedAt)} PT from live ELK data (${esc(indicesSeen)})</div>

  <div class="hero">
    <div class="card"><div class="card-label">Overall record</div>
      <div class="card-big">${overall.w}W – ${overall.l}L</div>
      <div class="card-sub">${overall.pct} winrate · ${overall.n} match${overall.n === 1 ? '' : 'es'}</div></div>
    <div class="card"><div class="card-label">Current rank</div>
      <div class="card-big">${esc(latest.rankLabel || '—')}</div>
      <div class="card-sub">Rank score ${latestScore ?? '—'} · from latest match</div></div>
  </div>

  <h2>Winrate by format</h2>
  <div class="hero">${formatCards}</div>

  <h2>Per-deck by format</h2>
  <table>
    <thead><tr><th>Deck</th><th>Format</th><th>Matches</th><th>W–L</th><th>Winrate</th></tr></thead>
    <tbody>${deckRows}</tbody>
  </table>

  <h2>Matches</h2>
  <table>
    <thead><tr><th>Time</th><th>Deck</th><th>Opponent</th><th>Event</th><th>Result</th><th>Rank</th></tr></thead>
    <tbody>${matchRows}</tbody>
  </table>

  <h2>Counterfactual Coach</h2>
  <div class="stub">
    <span class="tag">STUB — NOT BUILT YET</span>
    <p><strong>Next layer — needs full game-state reconstruction.</strong> The idea (Matt, Oct 30): replay a finished match and show the alternative line — "if you had done this instead of that, you might have lasted a turn longer and possibly have won." This panel is a placeholder for that feature. No analysis is shown here because the reconstruction engine does not exist yet — nothing on this page is simulated or invented.</p>
  </div>

  <footer>Arena Helper testing dashboard · data: local Elasticsearch *_94 indices (${docs.length} match docs) · page generated locally by elk/dashboard/generate-dashboard.mjs · Kibana remains the query-testing rig; this page previews the product shape.</footer>
</main>
</body>
</html>
`;

const outPath = path.join(here, 'index.html');
fs.writeFileSync(outPath, html);
console.log(JSON.stringify({
  out: outPath,
  docs: docs.length,
  overall: `${overall.w}W-${overall.l}L ${overall.pct}`,
  rank: latest.rankLabel,
  rankScore: latestScore,
  byFormat: Object.fromEntries([...byFormat.entries()].map(([k, v]) => { const t = tally(v); return [k, `${t.w}W-${t.l}L ${t.pct}`]; })),
  decks: [...deckFormat.keys()],
}, null, 2));
