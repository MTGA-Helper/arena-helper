import { parseAllLogsWithDebug } from './dist/index.js';
import Database from 'better-sqlite3';
import fs from 'node:fs';
import path from 'node:path';
import https from 'node:https';
import crypto from 'node:crypto';

// Load ../.env without overriding variables already set in the environment.
const envPath = path.join(import.meta.dirname, '..', '.env');
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (!m || line.trimStart().startsWith('#')) continue;
    process.env[m[1]] ??= m[2].replace(/^(['"])(.*)\1$/, '$2');
  }
}
const ES_URL = process.env.ELASTIC_URL ?? 'https://localhost:9200';
const ES_USER = process.env.ELASTIC_USER ?? 'elastic';
const ES_PASSWORD = process.env.ELASTIC_PASSWORD;
// CA defaults to ../elk/certs-ca.crt (override with ELASTIC_CA_CERT); ELASTIC_INSECURE=1 skips TLS verification (local dev only).
const ES_CA_PATH = process.env.ELASTIC_CA_CERT ?? path.join(import.meta.dirname, '..', 'elk', 'certs-ca.crt');
const ES_CA = fs.existsSync(ES_CA_PATH) ? fs.readFileSync(ES_CA_PATH) : undefined;
const ES_INSECURE = process.env.ELASTIC_INSECURE === '1';

function esRequest(method, urlPath, body, contentType = 'application/json') {
  const url = new URL(urlPath, ES_URL);
  return new Promise((resolve, reject) => {
    const req = https.request(
      url,
      {
        method,
        auth: `${ES_USER}:${ES_PASSWORD}`,
        headers: body ? { 'Content-Type': contentType, 'Content-Length': Buffer.byteLength(body) } : {},
        ca: ES_CA,
        rejectUnauthorized: !ES_INSECURE,
      },
      (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => resolve({ status: res.statusCode, body: data ? JSON.parse(data) : null }));
      },
    );
    req.on('error', reject);
    req.end(body);
  });
}

const INDEX_BODY = JSON.stringify({
  settings: { number_of_shards: 1, number_of_replicas: 0 },
  mappings: {
    properties: {
      timestamp: { type: 'date' },
      importedAt: { type: 'date' },
      user_id: { type: 'keyword' },
      myGamerTag: { type: 'keyword' },
      opponentGamerTag: { type: 'keyword' },
      myPlayerId: { type: 'keyword' },
      opponentPlayerId: { type: 'keyword' },
      id: { type: 'keyword' },
      deck: { type: 'keyword', fields: { text: { type: 'text' } } },
      myDeck: { type: 'keyword' },
      result: { type: 'keyword' },
      matchResult: { type: 'keyword' },
      eventId: { type: 'keyword' },
      opponent: { type: 'keyword' },
      opponentPlatform: { type: 'keyword' },
      opponentDeck: { type: 'keyword' },
      opponentColors: { type: 'keyword' },
      constructedClass: { type: 'keyword' },
      constructedSeasonOrdinal: { type: 'integer' },
      constructedLevel: { type: 'integer' },
      constructedStep: { type: 'integer' },
      rankDelta: { type: 'integer' },
      notes: { type: 'text' },
      playedCards: { type: 'flattened' },
    },
  },
});

// Creates the index with the mapping above when it does not exist yet.
async function ensureIndex(index) {
  const head = await esRequest('HEAD', `/${index}`);
  if (head.status === 200) return;
  const res = await esRequest('PUT', `/${index}`, INDEX_BODY);
  if (res.status >= 300 && res.body?.error?.type !== 'resource_already_exists_exception') {
    throw new Error(`Creating index ${index} failed: ${JSON.stringify(res.body)}`);
  }
  console.log(`Created index ${index}`);
}

async function bulkIndex(index, docs) {
  const body = docs
    .map(({ id, doc }) => `${JSON.stringify({ index: { _index: index, _id: id } })}\n${JSON.stringify(doc)}\n`)
    .join('');
  const res = await esRequest('POST', '/_bulk', body, 'application/x-ndjson');
  if (res.status >= 300) throw new Error(`Elasticsearch ${res.status}: ${JSON.stringify(res.body)}`);
  return res.body;
}
const outputPath = path.join(process.cwd(), '../mtga-cards-database-generator', 'output');
const latest = JSON.parse(fs.readFileSync(path.join(outputPath, 'latest.json'), 'utf8'));
const databasePath = path.join(outputPath, String(latest.latest), `v${latest.latest}-en-database.sqlite`);
const database = new Database(databasePath, { readonly: true });
const cardNamesByGrpId = new Map(
  database.prepare('SELECT grpid, name FROM cards').all().map((card) => [card.grpid, card.name]),
);

const logDir = path.join(
  path.dirname(process.env.LOCALAPPDATA),
  'LocalLow',
  'Wizards Of The Coast',
  'MTGA',
);

const result = await parseAllLogsWithDebug({ logDir });
const { matches } = result;

console.log(`Found ${matches.length} completed matches`);

const deckStats = new Map();
for (const match of matches) {
  const deckName = match.myDeck || '(Unknown deck)';
  const stats = deckStats.get(deckName) ?? { wins: 0, losses: 0, draws: 0, total: 0 };
  stats.total++;
  if (match.matchResult === 'Win') stats.wins++;
  else if (match.matchResult === 'Loss') stats.losses++;
  else if (match.matchResult === 'Draw') stats.draws++;
  deckStats.set(deckName, stats);
}

// Cumulative ladder steps before each class, and steps per level within it (4 levels per class).
// Every class below Mythic has 4 levels of 6 steps; Bronze-Gold give +2/-1 per win/loss, Platinum and above +1/-1.
const RANK_STEPS = { Bronze: [0, 6], Silver: [24, 6], Gold: [48, 6], Platinum: [72, 6], Diamond: [96, 6], Mythic: [120, 0] };
function rankScore(match) {
  const entry = RANK_STEPS[match.constructedClass];
  if (!entry) return null;
  return entry[0] + (4 - (match.constructedLevel ?? 4)) * entry[1] + (match.constructedStep ?? 0);
}

// Rank change per match: score after this match minus score after the previous ranked match of the same event.
const rankDeltaByMatch = new Map();
const lastScoreByEvent = new Map();
for (const match of [...matches].sort((a, b) => a.timestamp - b.timestamp)) {
  const score = rankScore(match);
  if (score === null) continue;
  const previous = lastScoreByEvent.get(match.eventId);
  if (previous !== undefined) rankDeltaByMatch.set(match.id, score - previous);
  lastScoreByEvent.set(match.eventId, score);
}

const documents = [];
for (const match of matches) {
  const playedCards = result.gameActions
    .filter((action) => action.matchId === match.id && action.type === 'CastSpell')
    .sort((a, b) => a.gameNumber - b.gameNumber || a.turnNumber - b.turnNumber)
    .reduce(
      (cards, action) => {
        const player = action.castByMe ? 'me' : 'opponent';
        const game = cards[player][action.gameNumber] ?? [];
        game.push({
          turnNumber: action.turnNumber,
          card: {
            grpId: action.sourceGrpId,
            cardName: cardNamesByGrpId.get(action.sourceGrpId),
            instanceId: action.sourceInstanceId,
          },
          action: {
            type: action.type,
            targetInstanceIds: action.targetInstanceIds,
            targetGrpIds: action.targetGrpIds,
          },
        });
        cards[player][action.gameNumber] = game;
        return cards;
      },
      { me: {}, opponent: {} },
    );

  const doc = {
    timestamp: match.timestamp,
    user_id: match.myGamerTag,
    myGamerTag: match.myGamerTag,
    opponentGamerTag: match.opponentGamerTag,
    myPlayerId: match.myPlayerId,
    opponentPlayerId: match.opponentPlayerId,
    deck: match.myDeck,
    result: match.matchResult,
    constructedSeasonOrdinal: match.constructedSeasonOrdinal,
    constructedClass: match.constructedClass,
    constructedLevel: match.constructedLevel,
    constructedStep: match.constructedStep,
    playedCards,
  };
  // Deterministic id makes re-runs overwrite rather than duplicate matches.
  const id = crypto.createHash('sha1').update(`${match.id}|${match.myPlayerId}|${match.timestamp}`).digest('hex');
  const forMatch = (rows) => rows.filter((row) => row.matchId === match.id).map(({ matchId, ...rest }) => rest);
  // The index document carries everything the parser produced for this match.
  const fullDoc = {
    ...match,
    ...doc,
    importedAt: match.importedAt,
    rankDelta: rankDeltaByMatch.get(match.id) ?? null,
    deckList: result.myDeckListMap.get(match.id),
    opponentGrpIds: [...(result.opponentGrpIds.get(match.id) ?? [])],
    gameSnapshots: forMatch(result.gameSnapshots),
    turnDrawRecords: forMatch(result.turnDrawRecords),
    gameActions: forMatch(result.gameActions),
    boardSnapshots: forMatch(result.boardSnapshots),
  };
  documents.push({ id, doc: fullDoc });
  console.log(JSON.stringify(doc, null, 2));
}

if (documents.length) {
  if (!ES_PASSWORD) {
    console.error('\nELASTIC_PASSWORD not set; skipping Elasticsearch push.');
  } else {
    // One index per event and season: <eventId>_<constructedSeasonOrdinal>, lowercased (Elasticsearch requires it).
    const byIndex = new Map();
    for (const entry of documents) {
      const { eventId, constructedSeasonOrdinal } = entry.doc;
      const index = `${eventId || 'unknown'}_${constructedSeasonOrdinal ?? 'unknown'}`.toLowerCase().replace(/[^a-z0-9_.-]/g, '_');
      byIndex.set(index, [...(byIndex.get(index) ?? []), entry]);
    }
    const BATCH = 500;
    for (const [index, docs] of byIndex) {
      await ensureIndex(index);
      let failed = 0;
      for (let i = 0; i < docs.length; i += BATCH) {
        const res = await bulkIndex(index, docs.slice(i, i + BATCH));
        if (res.errors) {
          const bad = res.items.filter((item) => item.index.error);
          failed += bad.length;
          console.error('Bulk errors:', JSON.stringify(bad.slice(0, 3).map((item) => item.index.error)));
        }
      }
      console.log(`\nIndexed ${docs.length - failed}/${docs.length} matches into ${index}`);
    }
  }
}
console.log('\nWin rate by deck:');
for (const [deckName, stats] of [...deckStats.entries()].sort(([first], [second]) => first.localeCompare(second))) {
  const winRate = stats.total ? (stats.wins / stats.total) * 100 : 0;
  console.log(
    `${deckName}: ${winRate.toFixed(1)}% (${stats.wins}W-${stats.losses}L-${stats.draws}D, ${stats.total} matches)`,
  );
}