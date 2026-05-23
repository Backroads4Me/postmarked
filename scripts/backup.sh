#!/bin/bash
set -e

# Postmarked Backup Tool
# Designed to run from the repository root

ARCHIVE_DIR="./scripts/archives"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_BACKUP_SQL="${ARCHIVE_DIR}/postmarked_db_${TIMESTAMP}.sql"
VOL_BACKUP_TAR="${ARCHIVE_DIR}/postmarked_volumes_${TIMESTAMP}.tar.gz"

PGUSER="${POSTGRES_USER:-postgres}"
PGDB="${POSTGRES_DB:-postmarked}"

mkdir -p "$ARCHIVE_DIR"

echo "[1/2] Dumping PostgreSQL database..."
docker compose exec -T db pg_dump -U "$PGUSER" "$PGDB" > "$DB_BACKUP_SQL"

echo "[2/2] Tarballing /originals and /derivatives volumes..."
docker run --rm \
  -v postmarked_originals:/originals \
  -v postmarked_derivatives:/derivatives \
  -v "$(pwd)/${ARCHIVE_DIR}:/backup" \
  alpine tar -czf "/backup/postmarked_volumes_${TIMESTAMP}.tar.gz" -C / originals derivatives

echo "Backup complete!"
echo "Database dump: $DB_BACKUP_SQL"
echo "Volume tarball: $VOL_BACKUP_TAR"
