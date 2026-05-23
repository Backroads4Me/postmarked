#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

api_url="${API_URL:-http://localhost:8000}"
admin_email="${ADMIN_EMAIL:-admin@example.com}"
admin_password="${ADMIN_PASSWORD:-changeme}"

tmp_dir="$(mktemp -d)"
cookie_jar="$tmp_dir/cookies.txt"
image_file="$tmp_dir/postmarked-smoke.png"
create_headers="$tmp_dir/create.headers"
patch_headers="$tmp_dir/patch.headers"
asset_id=""

cleanup() {
  if [[ -n "$asset_id" ]]; then
    curl -fsS -b "$cookie_jar" -X DELETE "$api_url/api/admin/media/$asset_id" >/dev/null || true
  fi
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

python3 - "$image_file" <<'PY'
import struct
import sys
import zlib

path = sys.argv[1]
width = 32
height = 32
raw = b"".join(b"\x00" + (b"\x36\x78\xa8" * width) for _ in range(height))

def chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )

png = (
    b"\x89PNG\r\n\x1a\n"
    + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    + chunk(b"IDAT", zlib.compress(raw, 9))
    + chunk(b"IEND", b"")
)

with open(path, "wb") as f:
    f.write(png)
PY

login_status="$(
  curl -sS -c "$cookie_jar" -o "$tmp_dir/login.out" -w '%{http_code}' \
    -X POST "$api_url/api/auth/jwt/login" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode "username=$admin_email" \
    --data-urlencode "password=$admin_password"
)"
if [[ "$login_status" != "204" ]]; then
  echo "Login failed with HTTP $login_status" >&2
  cat "$tmp_dir/login.out" >&2
  exit 1
fi

size="$(wc -c < "$image_file" | tr -d ' ')"
create_status="$(
  curl -sS -b "$cookie_jar" -D "$create_headers" -o "$tmp_dir/create.out" -w '%{http_code}' \
    -X POST "$api_url/api/admin/media/tus" \
    -H 'Tus-Resumable: 1.0.0' \
    -H "Upload-Length: $size" \
    -H 'Upload-Metadata: filename cG9zdG1hcmtlZC1zbW9rZS5wbmc=,filetype aW1hZ2UvcG5n'
)"
if [[ "$create_status" != "201" ]]; then
  echo "Upload create failed with HTTP $create_status" >&2
  cat "$tmp_dir/create.out" >&2
  exit 1
fi

location="$(awk 'tolower($1)=="location:" {print $2}' "$create_headers" | tr -d '\r')"
if [[ -z "$location" ]]; then
  echo "Upload create response did not include Location" >&2
  exit 1
fi

patch_status="$(
  curl -sS -b "$cookie_jar" -D "$patch_headers" -o "$tmp_dir/patch.out" -w '%{http_code}' \
    -X PATCH "$api_url$location" \
    -H 'Tus-Resumable: 1.0.0' \
    -H 'Upload-Offset: 0' \
    -H 'Content-Type: application/offset+octet-stream' \
    --data-binary "@$image_file"
)"
if [[ "$patch_status" != "204" ]]; then
  echo "Upload patch failed with HTTP $patch_status" >&2
  cat "$tmp_dir/patch.out" >&2
  exit 1
fi

asset_id="$(awk 'tolower($1)=="x-postmarked-asset-id:" {print $2}' "$patch_headers" | tr -d '\r')"
if [[ -z "$asset_id" ]]; then
  echo "Upload patch response did not include X-Postmarked-Asset-Id" >&2
  exit 1
fi

for _ in $(seq 1 30); do
  state="$(
    docker compose exec -T db \
      psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postmarked}" -At \
      -c "select processing_state from media_asset where id='$asset_id';"
  )"
  if [[ "$state" == "READY" ]]; then
    break
  fi
  if [[ "$state" == "FAILED" ]]; then
    docker compose exec -T db \
      psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postmarked}" \
      -c "select error_message from media_asset where id='$asset_id';" >&2
    exit 1
  fi
  sleep 1
done

if [[ "${state:-}" != "READY" ]]; then
  echo "Media asset $asset_id did not become READY; last state: ${state:-missing}" >&2
  exit 1
fi

media_status="$(
  curl -sS -b "$cookie_jar" -o "$tmp_dir/media.webp" -w '%{http_code} %{content_type} %{size_download}' \
    "$api_url/media/$asset_id/webp"
)"

case "$media_status" in
  200\ image/webp\ *[1-9]*) ;;
  *)
    echo "Media fetch failed: $media_status" >&2
    exit 1
    ;;
esac

echo "Media upload smoke passed for asset $asset_id."
