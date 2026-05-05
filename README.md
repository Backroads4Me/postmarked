# Goodpath

Goodpath is a personal, self-hosted RV lifestyle sharing app for full-time RV travel. It is designed so family and friends can quickly see where the RV is now, what has been shared recently, and how the current trip segment fits into one continuous journey.

## Current Status

The local MVP is ready for owner testing. The stabilization pass is complete:

- Docker stack boots with Astro, FastAPI, Postgres/PostGIS, Redis, Celery, and Caddy.
- Alembic migrations are at head.
- Seed data creates a full-time RV journey, trip segments, current stop, future stop, and recent posts.
- Public reader APIs are wired to the frontend.
- Admin can manage trips, stops, journeys, posts, imports, media, and pending users.
- RV Trip Wizard Excel preview/apply creates and updates `PlannedStop` rows.
- Frontend production build passes.

Open polish work remains, but it is not blocking local testing.

## Local URLs

When the Docker dev stack is running:

- Production-like dev proxy: http://localhost:8080
- Direct Astro dev server: http://localhost:4321
- API: http://localhost:8000/api/health/ready
- Flower: http://localhost:5555

Use the Caddy dev proxy at http://localhost:8080 for normal testing because it routes `/`, `/api/*`, `/media/*`, and `/tiles/*` the same way production will.

Admin:

- URL: http://localhost:8080/admin
- Email: `admin@example.com`
- Password: `admin123`

Change the seeded admin credentials before any real deployment.

## Prerequisites

- Docker and Docker Compose
- Node 22+ for direct frontend development
- Python 3.12+ and `uv` for direct API development

## Local Setup With Docker

1. Create local environment overrides:

   ```bash
   cp .env.example .env
   ```

2. Start the stack:

   ```bash
   docker compose -f compose/docker-compose.yml -f compose/docker-compose.dev.yml up --build
   ```

3. Seed or refresh demo data:

   ```bash
   docker compose -f compose/docker-compose.yml -f compose/docker-compose.dev.yml exec api python scripts/seed.py
   ```

The `api-migrate` service runs `alembic upgrade head` automatically during compose startup.

## Verification

Useful smoke checks:

```bash
docker compose -f compose/docker-compose.yml -f compose/docker-compose.dev.yml ps
docker exec compose-api-1 alembic current
docker exec compose-api-1 python -c "import app.main; print('api import ok')"
docker exec compose-api-1 python scripts/seed.py
docker exec compose-web-1 npm run build
```

Expected public API checks:

```bash
curl http://localhost:8000/api/health/ready
curl http://localhost:8000/api/home
curl http://localhost:8000/api/timeline
curl http://localhost:8000/api/trip-segments
```

## RV Trip Wizard Excel Import

The MVP supports RV Trip Wizard `.xlsx` exports only.

Browser flow:

1. Log in as admin.
2. Open http://localhost:8080/admin/imports/rv-trip-wizard.
3. Upload an `.xlsx` export.
4. Review the diff.
5. Apply it to an existing trip segment or create a new one.

API flow:

```bash
curl -X POST http://localhost:8000/api/admin/imports/rv-trip-wizard/preview \
  -H "Cookie: <session>" \
  -F "file=@/path/to/trip.xlsx"
```

```bash
curl -X POST http://localhost:8000/api/admin/imports/<import_run_id>/apply \
  -H "Cookie: <session>" \
  -H "Content-Type: application/json" \
  -d '{"target_trip_id": "<trip-uuid>", "create_trip": false}'
```

Use `"create_trip": true` to create a trip segment from the file title.

Reimport is preview-first. Removed stops are marked `REMOVED_FROM_LATEST_IMPORT`, not deleted. Private RV Trip Wizard fields such as reservation numbers, comments, cost, and fuel data are stored for the owner but are not returned by public reader endpoints.

## Direct Development

Frontend:

```bash
cd web
npm install
API_BASE_URL=http://localhost:8000 npm run dev
```

API:

```bash
cd api
uv venv
uv pip install -e ".[dev]"
PYTHONPATH=. DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/goodpath uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

For direct API development you still need PostgreSQL/PostGIS and Redis. The easiest route is to run the Docker database services.

## PMTiles

Maps use MapLibre with a PMTiles source at `/tiles/basemap.pmtiles`. The app still renders markers and routes over a dark fallback background if the tile file is missing.

To enable full local basemap tiles, place a compatible PMTiles file at:

```text
pmtiles/basemap.pmtiles
```

Large `.pmtiles` files are intentionally ignored by git.

## Deployment Notes

For a single-host deployment:

1. Copy `.env.example` to `.env`.
2. Set a strong `SECRET_KEY`.
3. Set production `ALLOWED_ORIGINS`, `ALLOWED_HOSTS`, and `FLOWER_BASIC_AUTH`.
4. Review `caddy/Caddyfile` for the real domain and TLS settings.
5. Run:

   ```bash
   docker compose -f compose/docker-compose.yml up --build -d
   ```

Backups and restores are handled by `scripts/backup.sh` and `scripts/restore.sh`.

## Remaining Non-Blocking Work

See `docs/path-to-testing.md` for the current test checklist and polish backlog. The highest-value items before wider family testing are:

- Self-host fonts.
- Clean up visible icon/emoji polish.
- Add friendly SSR error states.
- Run a mobile-width admin and reader pass.
- Add deeper regression tests for import and visibility edge cases.
