#!/bin/sh
set -e

MEDIA_DIR="${MEDIA_DIR:-/media}"
for dir in "${ORIGINALS_PATH:-$MEDIA_DIR/originals}" "${DERIVATIVES_PATH:-$MEDIA_DIR/derivatives}" "${INGEST_PATH:-$MEDIA_DIR/ingest}" "${BACKUPS_PATH:-$MEDIA_DIR/backups}"; do
  mkdir -p "$dir"
  chown -R appuser:appuser "$dir"
done

# The collation check runs before alembic because a drifted index makes even
# migration lookups return wrong rows.
if [ "$(id -u)" = "0" ]; then
  gosu appuser python -c "from app.config import validate_env; validate_env()"
  gosu appuser python scripts/check_collation.py
  gosu appuser alembic upgrade head
  gosu appuser python scripts/seed.py
  exec gosu appuser "$@"
fi

python -c "from app.config import validate_env; validate_env()"
python scripts/check_collation.py
alembic upgrade head
python scripts/seed.py

exec "$@"
