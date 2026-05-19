#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

api_container="$(docker compose ps -q api)"
db_container="$(docker compose ps -q db)"

if [[ -z "$api_container" || -z "$db_container" ]]; then
  echo "Postmarked api/db containers are not running. Start the stack with: docker compose up" >&2
  exit 2
fi

query="
select
  id::text,
  coalesce(original_path, ''),
  coalesce(derivative_paths->>'webp', ''),
  coalesce(derivative_paths->>'poster', '')
from media_asset
order by created_at;
"

missing=0
while IFS=$'\t' read -r asset_id original_path webp_path poster_path; do
  [[ -z "$asset_id" ]] && continue

  if [[ -n "$original_path" ]]; then
    if ! docker exec "$api_container" test -f "$original_path"; then
      echo "missing original: $asset_id -> $original_path"
      missing=1
    fi
  fi

  if [[ -n "$webp_path" ]]; then
    webp_file="/derivatives/${asset_id}.webp"
    if ! docker exec "$api_container" test -f "$webp_file"; then
      echo "missing webp derivative: $asset_id -> $webp_file (DB path: $webp_path)"
      missing=1
    fi
  fi

  if [[ -n "$poster_path" ]]; then
    poster_file="/derivatives/${asset_id}-poster.jpg"
    if ! docker exec "$api_container" test -f "$poster_file"; then
      echo "missing poster derivative: $asset_id -> $poster_file (DB path: $poster_path)"
      missing=1
    fi
  fi
done < <(
  docker exec "$db_container" \
    psql -U postgres -d postmarked -At -F $'\t' -c "$query"
)

if [[ "$missing" -ne 0 ]]; then
  cat >&2 <<'EOF'

One or more media files referenced by the database are missing from the active
Docker volumes. If you recently renamed the compose project or moved from an
older compose file, check for older volumes such as compose_originals and
compose_derivatives and copy their contents into the active volumes.
EOF
  exit 1
fi

echo "Media storage check passed."
