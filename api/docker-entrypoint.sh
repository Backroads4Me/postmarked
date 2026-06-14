#!/bin/sh
set -e

MEDIA_DIR="${MEDIA_DIR:-/media}"
for dir in "${ORIGINALS_PATH:-$MEDIA_DIR/originals}" "${DERIVATIVES_PATH:-$MEDIA_DIR/derivatives}" "${INGEST_PATH:-$MEDIA_DIR/ingest}"; do
  mkdir -p "$dir"
  chown -R appuser:appuser "$dir"
done

if [ "$(id -u)" = "0" ]; then
  gosu appuser alembic upgrade head
  gosu appuser python scripts/seed.py
  exec gosu appuser "$@"
fi

alembic upgrade head
python scripts/seed.py

exec "$@"
