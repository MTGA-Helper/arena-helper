FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src
COPY sets ./sets
COPY set-mappings.json ./set-mappings.json
COPY formats.json ./formats.json

RUN mkdir -p /app/output

VOLUME ["/app/output"]

CMD ["sh", "-c", "npm run tsc && node dist/updateFormats.js && cp /app/formats.json /app/output/ && node dist/updateSets.js && cp -r /app/sets /app/output/ && node dist/auditSetMappings.js && npm start && npm run dist"]