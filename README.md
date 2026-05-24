# Postmarked

Postmarked is a self-hosted travel journal for sharing your journey with friends and family. Post a quick update, drop a photo, note the place — like sending a postcard from everywhere you go. Visitors can check in whenever they want, or sign up to be notified when something new is posted.

It is not a trip planning tool, a blogging platform, or a journaling app. Just quick, lightweight updates from the road.

## Current Status

Ready for beta testing. The stabilization pass is complete:

- Docker stack boots with Astro, FastAPI, Postgres/PostGIS, Redis, and Celery.
- Alembic migrations are at head (`a2b3c4d5e6f7`).
- Seed data creates trips with stops, a current stop, a future stop, and recent posts.
- Public reader APIs are wired to the frontend.
- Admin can manage trips, stops, posts, activities, imports, media, and pending users.
- RV Trip Wizard Excel preview/apply creates and updates normal draft stops.
- Frontend production build passes.

Open polish work remains but is not blocking beta testing.

## Local URLs

When the Docker dev stack is running:

- Web app: http://localhost:4321
- API: http://localhost:8000/api/health/ready
- Optional Flower dashboard: http://localhost:5555 when started with `--profile tools`

Use the Astro web app at http://localhost:4321 for normal testing. Astro proxies `/api/*` and `/media/*` to FastAPI.

Admin:

- URL: http://localhost:4321/admin
- Email: `ADMIN_EMAIL` from `.env` (`admin@example.com` by default)
- Password: `ADMIN_PASSWORD` from `.env` (`changeme` by default)

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
   docker compose up --build
   ```

   Add `--profile tools` if you want the optional Flower Celery dashboard.

3. Seed or refresh demo data:

   ```bash
   docker compose exec api python scripts/seed.py
   ```

The `api-migrate` service runs `alembic upgrade head` automatically during compose startup.

## Verification

Useful smoke checks:

```bash
docker compose ps
docker exec api alembic current
docker exec api python -c "import app.main; print('api import ok')"
docker exec api python scripts/seed.py
docker exec web npm run build
./scripts/check-media-storage.sh
./scripts/smoke-media-upload.sh
```

Expected public API checks:

```bash
curl http://localhost:8000/api/health/ready
curl http://localhost:8000/api/home
curl http://localhost:8000/api/timeline
curl http://localhost:8000/api/trip-segments
```

## RV Trip Wizard Excel Import

The app supports RV Trip Wizard `.xlsx` exports for importing route itineraries as normal stops.

Browser flow:

1. Log in as admin.
2. Open http://localhost:4321/admin/imports/rv-trip-wizard.
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

Reimport is preview-first. Removed stops are marked `REMOVED_FROM_LATEST_IMPORT`, not deleted. Private fields such as reservation numbers, comments, cost, and fuel data are stored for the owner but are not returned by public reader endpoints.

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
PYTHONPATH=. DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/postmarked uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

For direct API development you still need PostgreSQL/PostGIS and Redis. The easiest route is to run the Docker database services.

## Maps

The default map provider is Google Maps because it avoids requiring a local basemap file:

```env
PUBLIC_GOOGLE_MAPS_API_KEY=<your browser API key>
PUBLIC_GOOGLE_MAPS_MAP_ID=<optional cloud map ID>
```

Create a Google Maps Platform API key, restrict it by HTTP referrer, and set budget/quota alerts in Google Cloud. If the key is missing, the app still renders a simple route schematic instead of a blank map. The optional map ID enables Google Advanced Markers and cloud map styling; local testing falls back to Google's demo map ID when it is blank.

## Deployment Notes

For a single-host deployment:

1. Copy `.env.example` to `.env`.
2. Set a strong `SECRET_KEY`:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
3. Set production `ALLOWED_ORIGINS`, `ALLOWED_HOSTS`, and `FLOWER_BASIC_AUTH`.
4. Point your own reverse proxy at the `web` service and expose only the routes you intend to publish. The bundled Compose file does not ship a Caddy container.
5. Run:

   ```bash
   docker compose -f compose.yaml up --build -d
   ```

Backups and restores are handled by `scripts/backup.sh` and `scripts/restore.sh`.
If media images start returning 404s after a compose/project-name migration,
run `./scripts/check-media-storage.sh` to confirm the database still points at
files present in the active Docker media volumes.

## Remaining Non-Blocking Work

See `docs/path-to-testing.md` for the current test checklist and polish backlog. The highest-value items before wider beta testing are:

- Self-host fonts.
- Clean up visible icon/emoji polish.
- Run a mobile-width admin and reader pass.
- Add deeper regression tests for import and visibility edge cases.
- Finish production reverse-proxy/TLS/header review before deploying on a public domain.
