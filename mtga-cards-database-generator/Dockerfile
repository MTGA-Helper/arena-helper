FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json formats.json set-mappings.json latest.json ./
COPY src ./src
COPY sets ./sets

RUN mkdir -p /app/output

VOLUME ["/app/output"]

CMD ["sh", "-c", "npm run tsc && node dist/updateSets.js && npm start"]