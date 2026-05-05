# Goodpath API

FastAPI backend for Goodpath. Requires PostgreSQL/PostGIS and Redis.

## Stack

- Python 3.12
- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL/PostGIS
- Redis/Celery
- fastapi-users cookie sessions

## Local Install

```bash
uv venv
uv pip install -e ".[dev]"
```

## Run Directly

```bash
PYTHONPATH=. DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/goodpath \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Direct API work still needs PostgreSQL/PostGIS and Redis. The easiest path is usually to run the Docker services.

## Run With Docker

From the repo root:

```bash
docker compose -f compose/docker-compose.yml -f compose/docker-compose.dev.yml up --build
```

The dev compose file mounts `api/` into the container and runs Uvicorn with reload.

## Migrations

```bash
alembic upgrade head
alembic current
alembic check
```

In Docker, the `api-migrate` service runs `alembic upgrade head` automatically before the API starts.

## Checks

```bash
python -m compileall app
python -c "import app.main; print('api import ok')"
python scripts/seed.py
```

Docker equivalents:

```bash
docker exec compose-api-1 alembic current
docker exec compose-api-1 python -c "import app.main; print('api import ok')"
docker exec compose-api-1 python scripts/seed.py
```

## Route Map

| Prefix | Module | Notes |
| --- | --- | --- |
| `/api/home`, `/api/timeline`, `/api/trip-segments` | `routers/journey.py` | Canonical public RV reader API |
| `/api/trips` | `routers/trips.py` | Legacy/public trip list and detail |
| `/api/trips/{trip_slug}/stops/{stop_slug}` | `routers/stops.py` | Public stop detail |
| `/api/comments`, `/api/likes` | `routers/social.py` | Comments and likes with visibility checks |
| `/media/{asset_id}/{variant}` | `routers/media.py` | Media streaming mounted at root, not under `/api` |
| `/api/admin/trips` | `routers/admin/trips.py` | Admin trip CRUD |
| `/api/admin/stops` | `routers/admin/stops.py` | Admin stop CRUD |
| `/api/admin/posts` | `routers/admin/posts.py` | Quick updates CRUD and current-stop endpoint |
| `/api/admin/journeys` | `routers/admin/journeys.py` | Journey CRUD and activation |
| `/api/admin/imports` | `routers/admin/imports.py` | RV Trip Wizard preview/apply/history |
| `/api/admin/media` | `routers/admin/media.py` | TUS-style uploads and media assignment |
| `/api/admin/users` | `routers/admin/users.py` | Pending/approved user list and approval actions |
| `/api/auth/jwt` | fastapi-users | Cookie-backed login/logout |
| `/api/auth` | fastapi-users | Registration |
| `/api/users/me` | fastapi-users | Current-user check |

Auth uses the `goodpath_session` HTTP-only cookie. Login via `POST /api/auth/jwt/login` with `username` and `password` form fields.

## Import Parser

RV Trip Wizard Excel parsing lives in `app/imports/`. The supported MVP path is `.xlsx` only.

Useful local parser check:

```bash
PYTHONPATH=. python - <<'PY'
from app.imports.rv_trip_wizard import parse_excel
p = parse_excel("../export-examples/trip-26-05-04-07-46.xlsx")
print(p.title, len(p.stops), len(p.warnings))
PY
```
