import { parseAllLogsWithDebug } from './dist/index.js';
import Database from 'better-sqlite3';
import fs from 'node:fs';
import path from 'node:path';

const outputPath = path.join(process.cwd(), 'mtga-cards-database-generator', 'output');
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

  console.log(JSON.stringify({
    timestamp: match.timestamp,
    myGamerTag: match.myGamerTag,
    opponentGamerTag: match.opponentGamerTag,
    myPlayerId: match.myPlayerId,
    opponentPlayerId: match.opponentPlayerId,
    deck: match.myDeck,
    result: match.matchResult,
    playedCards,
  }, null, 2));
}