#!/bin/sh
set -eu

export PATH="/usr/local/bin:/usr/bin:/bin"

cd /app
npm run tsc
node dist/updateFormats.js
cp /app/formats.json /app/output/
node dist/updateSets.js
cp -r /app/sets /app/output/
node dist/auditSetMappings.js
npm start
npm run dist

touch /tmp/metadata-initial-run-complete