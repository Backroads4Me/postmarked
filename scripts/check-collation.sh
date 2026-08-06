#!/usr/bin/env bash
set -euo pipefail

# Verify every btree index against its own sort order using amcheck.
#
# The startup check in the api container compares collation versions, which only
# works once a version is recorded. This inspects the indexes themselves, so it
# also catches a database whose ordering drifted while untracked. Symptoms are
# silent: a published post 404s while still appearing in listings, because the
# lookup that resolves it walks a mis-ordered index and finds nothing.
#
# Usage: ./scripts/check-collation.sh [--repair]

cd "$(dirname "$0")/.."

repair=0
if [[ "${1:-}" == "--repair" ]]; then
  repair=1
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--repair]" >&2
  exit 2
fi

db_container="$(docker compose ps -q db)"

if [[ -z "$db_container" ]]; then
  echo "Postmarked db container is not running. Start the stack with: docker compose up" >&2
  exit 2
fi

psql_run() {
  docker exec -i "$db_container" \
    psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postmarked}" -v ON_ERROR_STOP=1 "$@"
}

psql_run -q -c "SET client_min_messages = warning; CREATE EXTENSION IF NOT EXISTS amcheck;"

list_query="
SELECT c.relname
FROM pg_class c
JOIN pg_index i ON i.indexrelid = c.oid
JOIN pg_class t ON t.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_am a ON a.oid = c.relam
WHERE n.nspname = 'public' AND a.amname = 'btree'
  AND i.indisvalid AND i.indisready
ORDER BY t.relname, c.relname;
"

# Collect the list up front: psql runs through `docker exec -i`, which would
# otherwise consume the loop's stdin and skip every index after the first.
mapfile -t indexes < <(psql_run -At -c "$list_query")

corrupt=()
checked=0
for index in "${indexes[@]}"; do
  [[ -z "$index" ]] && continue
  checked=$((checked + 1))
  if ! psql_run -q -c "SELECT bt_index_check('public.\"$index\"'::regclass, true);" >/dev/null 2>&1 </dev/null; then
    echo "corrupt index: $index"
    corrupt+=("$index")
  fi
done

if [[ ${#corrupt[@]} -eq 0 ]]; then
  echo "Collation check passed ($checked btree indexes verified)."
  exit 0
fi

if [[ "$repair" -eq 0 ]]; then
  cat >&2 <<EOF

${#corrupt[@]} of $checked indexes no longer match their collation's sort order.
Queries resolved through them can silently return no rows, hiding published
content from the public site.

Rebuild them with: $0 --repair
EOF
  exit 1
fi

for index in "${corrupt[@]}"; do
  echo "rebuilding: $index"
  psql_run -q -c "REINDEX INDEX CONCURRENTLY public.\"$index\";"
done

psql_run -q -c "UPDATE pg_database SET datcollversion = pg_database_collation_actual_version(oid) WHERE datname = current_database();"

echo "Rebuilt ${#corrupt[@]} indexes and refreshed the recorded collation version."
