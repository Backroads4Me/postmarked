#!/bin/bash
set -e

# Postmarked Restore Tool
# Usage: ./scripts/restore.sh <db_sql_file> <volume_tar_file>

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <db_sql_file> <volume_tar_file>"
    exit 1
fi

DB_FILE="$1"
VOL_FILE="$2"

if [ ! -f "$DB_FILE" ]; then echo "Database file not found: $DB_FILE"; exit 1; fi
if [ ! -f "$VOL_FILE" ]; then echo "Volume file not found: $VOL_FILE"; exit 1; fi

PGUSER="${POSTGRES_USER:-postgres}"
PGDB="${POSTGRES_DB:-postmarked}"

echo "[1/2] Restoring volumes..."
docker run --rm \
  -v postmarked_originals:/originals \
  -v postmarked_derivatives:/derivatives \
  -v "$(realpath ${VOL_FILE}):/backup.tar.gz" \
  alpine tar -xzf "/backup.tar.gz" -C /

echo "[2/2] Restoring PostgreSQL database..."
docker compose exec -T db dropdb -U "$PGUSER" "$PGDB" || true
docker compose exec -T db createdb -U "$PGUSER" "$PGDB"
cat "$DB_FILE" | docker compose exec -T db psql -U "$PGUSER" -d "$PGDB"

echo "Restore complete!"
