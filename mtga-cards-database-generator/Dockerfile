FROM node:22-bookworm-slim

RUN apt-get update \
	&& apt-get install -y --no-install-recommends cron tzdata util-linux \
	&& rm -rf /var/lib/apt/lists/*

ENV TZ=America/New_York
RUN ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime \
	&& echo "$TZ" > /etc/timezone

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src
COPY sets ./sets
COPY set-mappings.json ./set-mappings.json
COPY formats.json ./formats.json
COPY run-generator.sh start-scheduler.sh ./

RUN mkdir -p /app/output
RUN chmod +x /app/run-generator.sh /app/start-scheduler.sh \
		&& printf '00 14 * * * root cd /app && /usr/bin/flock -n /tmp/metadata-generator.lock /app/run-generator.sh >> /proc/1/fd/1 2>&1\n' \
			> /etc/cron.d/metadata-generator \
		&& chmod 0644 /etc/cron.d/metadata-generator

VOLUME ["/app/output"]

CMD ["/app/start-scheduler.sh"]