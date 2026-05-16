#!/bin/sh
set -e

for dir in "${ORIGINALS_PATH:-/tmp/originals}" "${DERIVATIVES_PATH:-/tmp/derivatives}" "${INGEST_PATH:-/tmp/ingest}"; do
  mkdir -p "$dir"
  chown -R appuser:appuser "$dir"
done

if [ "$(id -u)" = "0" ]; then
  exec gosu appuser "$@"
fi

exec "$@"
