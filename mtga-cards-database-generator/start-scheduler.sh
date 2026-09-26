#!/bin/sh
set -eu

/usr/bin/flock -n /tmp/metadata-generator.lock /app/run-generator.sh
exec cron -f