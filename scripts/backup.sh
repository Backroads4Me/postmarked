#!/bin/bash
set -e

# Goodpath Backup Tool
# Designed to run from the repository root

ARCHIVE_DIR="./scripts/archives"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_BACKUP_SQL="${ARCHIVE_DIR}/postmarked_db_${TIMESTAMP}.sql"
VOL_BACKUP_TAR="${ARCHIVE_DIR}/postmarked_volumes_${TIMESTAMP}.tar.gz"

mkdir -p "$ARCHIVE_DIR"

echo "[1/2] Dumping PostgreSQL database..."
# Assuming standard postmarked compose stack running locally
docker compose exec -T db pg_dump -U postgres postmarked > "$DB_BACKUP_SQL"

echo "[2/2] Tarballing /originals and /derivatives volumes..."
# Spin up an ephemeral alpine container to zip the volumes safely
docker run --rm \
  -v postmarked_originals:/originals \
  -v postmarked_derivatives:/derivatives \
  -v "$(pwd)/${ARCHIVE_DIR}:/backup" \
  alpine tar -czf "/backup/postmarked_volumes_${TIMESTAMP}.tar.gz" -C / originals derivatives

echo "Backup complete!"
echo "Database dump: $DB_BACKUP_SQL"
echo "Volume tarball: $VOL_BACKUP_TAR"
