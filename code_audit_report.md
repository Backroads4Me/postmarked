# Postmarked Code Audit Report

This document compiles the results of a comprehensive code audit of the Postmarked travel journal repository. No source code modifications have been made at this time.

---

## 1. Executive Summary
Postmarked is structured as a solid MVP using **FastAPI** (Python) on the backend and **Astro 6** (React 19, Tailwind CSS 4) on the frontend, supported by a PostgreSQL/PostGIS, Celery, and Redis stack. 

The audit identified several **critical crash vulnerabilities** in backend configuration parsing and Celery workers, **completely unused database tables/dead code** (including likes, collections, and media scan jobs), **under-implemented/broken features** (such as search and post activities), and **hardcoded environment fallbacks** in utility shell scripts.

---

## 2. Critical Bugs & Potential Crashes

### 🚨 Mismatched `DATABASE_URL` Parsing in Celery Worker (`tasks.py` vs `db.py`)
* **Location**: [api/app/tasks.py](file:///home/ted/src/postmarked/api/app/tasks.py#L25) vs [api/app/db.py](file:///home/ted/src/postmarked/api/app/db.py#L11-L12)
* **Description**: The main database connection in `db.py` replaces standard `postgresql://` URLs with `postgresql+psycopg://` at runtime to ensure compatibility with `psycopg` (v3) async dialects. However, `tasks.py` loads `DATABASE_URL` from `os.getenv` directly into SQLAlchemy's sync `create_engine` without this replacement.
* **Impact**: If a user specifies a standard database URL in their `.env` file (e.g., `DATABASE_URL=postgresql://postgres:postgres@db:5432/postmarked`), the FastAPI backend will start successfully, but Celery worker tasks will instantly crash with `NoSuchModuleError` because SQLAlchemy will try to load the missing `psycopg2` driver instead of `psycopg` (v3).

### 🚨 Crash Hazard in `SMTP_PORT` Parsing on Empty Settings
* **Location**: [api/app/services/mailer.py](file:///home/ted/src/postmarked/api/app/services/mailer.py#L16)
* **Description**: `SMTP_PORT` is parsed directly via `int(os.getenv("SMTP_PORT", ...))`. If `SMTP_PORT=` is defined but left empty in `.env`, `os.getenv` returns `""` (since the fallback is only used if the key is absent/`None`).
* **Impact**: The FastAPI application will crash immediately on startup with a `ValueError: invalid literal for int() with base 10: ''` when it imports the mailer service.

### 🚨 Unhandled Exception in Seed Script on Missing `ADMIN_EMAIL`
* **Location**: [api/scripts/seed.py](file:///home/ted/src/postmarked/api/scripts/seed.py#L13)
* **Description**: The script retrieves the admin email via `os.getenv("ADMIN_EMAIL").strip().lower()`.
* **Impact**: If `ADMIN_EMAIL` is not set in `.env`, `os.getenv` returns `None`. Calling `.strip()` on a `NoneType` object will raise an unhandled `AttributeError`, bypassing the subsequent validation checks (lines 17–22) and causing the seeding task to fail with a traceback.

---

## 3. Dead / Extraneous Code & Tables
These features are represented in database models, tables, and sometimes API endpoints, but are completely unused by the active application logic or UI.

### 🗑️ Unused Database Models & Schemas
* **Location**: [api/app/models/system.py](file:///home/ted/src/postmarked/api/app/models/system.py) and [api/app/models/__init__.py](file:///home/ted/src/postmarked/api/app/models/__init__.py)
* **Description**: Several database tables exist and are created in migrations, but have no corresponding business logic:
  * **`ScanSource` / `ScanJob` / `ImportCandidate`**: Intended for scanning the filesystem, but the filesystem media ingest task (`scan_filesystem` in `tasks.py`) scans the directory directly and does not write to or read from these tables.
  * **`Collection` / `CollectionItem`**: No schemas, routes, or UI components reference media collections.
  * **`RedirectSlug`**: Never referenced or used in any router or controller.

### 🗑️ Disconnected Traveler and RV Profiles
* **Location**: [api/app/models/profile.py](file:///home/ted/src/postmarked/api/app/models/profile.py), [api/app/routers/profiles.py](file:///home/ted/src/postmarked/api/app/routers/profiles.py)
* **Description**: The database includes `RvProfile` and `TravelerProfile` models, and a public GET endpoint exists to fetch them. However, **there is no admin API** to create or edit profiles, **no form or settings page** in the Astro admin interface, and the public `/about` page (which would normally render this information) consists of static, hardcoded HTML copy.

### 🗑️ Unused Social Likes
* **Location**: [api/app/routers/social.py](file:///home/ted/src/postmarked/api/app/routers/social.py#L139), [api/app/models/system.py](file:///home/ted/src/postmarked/api/app/models/system.py#L25)
* **Description**: The backend implements `Like` models, database tables, schemas, and a full endpoint system (`POST /social/likes`, `GET /social/likes/{kind}/{id}/count`). However, the Astro frontend and React islands contain no liking buttons, counters, or actions, rendering this subsystem entirely dead.

---

## 4. Under-Implemented / Broken Features

### 🛠️ Post Activities and POIs (Point of Interest)
* **Location**: [api/app/routers/admin/posts.py](file:///home/ted/src/postmarked/api/app/routers/admin/posts.py#L105-L110)
* **Description**: The codebase defines a "Post Activities" model designed to represent hikes, museum visits, restaurant outings, etc. (as specified in [docs/post-activities-design.md](file:///home/ted/src/postmarked/docs/post-activities-design.md)). However:
  * The admin POST `/posts` and PATCH `/posts/{post_id}` routes **explicitly overwrite** the incoming payload, clearing out the activity fields:
    ```python
    post_type=PostType.UPDATE,
    activity_type=None,
    summary=None,
    activity_started_at=None,
    activity_ended_at=None,
    poi_id=None
    ```
  * The Astro admin post composer has no form fields or UI controls for configuring these fields, and hardcodes `post_type: 'update'` in the update payload.
  * **Result**: While the database and public schemas support activities, the admin controller explicitly blocks saving them.

### 🛠️ Disconnected Search Page & Search Redirect
* **Location**: [web/src/components/SearchIsland.jsx](file:///home/ted/src/postmarked/web/src/components/SearchIsland.jsx), [api/app/routers/search.py](file:///home/ted/src/postmarked/api/app/routers/search.py)
* **Description**: A `SearchIsland` React component exists to trigger a global search overlay, and a backend search API is fully implemented. However:
  * `SearchIsland` is never imported or mounted in any Astro layout or page (making it inaccessible to the user).
  * The search API returns a slug `/trips/search-redirect?stop={id}` for stop matches, but **no redirect page exists** in Astro at `/trips/search-redirect`, which would result in a 404 error if search results were ever clicked.

---

## 5. Environment Variable & Script Issues

### 🔒 Hardcoded Credentials in Scripts
* **Location**: [scripts/backup.sh](file:///home/ted/src/postmarked/scripts/backup.sh#L16), [scripts/restore.sh](file:///home/ted/src/postmarked/scripts/restore.sh#L29-L31), [scripts/check-media-storage.sh](file:///home/ted/src/postmarked/scripts/check-media-storage.sh#L52)
* **Description**: These scripts execute commands inside database containers using hardcoded database usernames (`-U postgres`) and database names (`postmarked`).
* **Impact**: If a user changes `POSTGRES_USER` or `POSTGRES_DB` inside `.env` for security or staging purposes, all database backups, restores, and storage diagnostics will fail.

### 🔒 Password Mismatch in Smoke Test
* **Location**: [scripts/smoke-media-upload.sh](file:///home/ted/src/postmarked/scripts/smoke-media-upload.sh#L8)
* **Description**: The smoke test script defaults to `ADMIN_PASSWORD=admin123` instead of the `changeme` value specified in `.env.example` and the README.
* **Impact**: Running the script locally without overrides results in auth check failures. It also contains hardcoded database credentials.

### 🔒 Astro environment variable loading
* **Location**: [web/src/pages/postmarked-config.js.ts](file:///home/ted/src/postmarked/web/src/pages/postmarked-config.js.ts#L3-L4)
* **Description**: The endpoint uses `process.env` to load `PUBLIC_GOOGLE_MAPS_API_KEY` and `PUBLIC_GOOGLE_MAPS_MAP_ID`.
* **Impact**: While this works in Node.js server environments, the Astro-native `import.meta.env` is the officially supported standard and is safer for build/runtime portability.

---

## 6. Recommendations

1. **Fix Worker Mismatch**: Update [api/app/tasks.py](file:///home/ted/src/postmarked/api/app/tasks.py#L25) to import `DATABASE_URL` from `app.db` or perform the same `postgresql://` dialect prefix correction, preventing database connection errors on startup.
2. **Safer SMTP Port Extraction**: In [api/app/services/mailer.py](file:///home/ted/src/postmarked/api/app/services/mailer.py#L16), parse the port string safely:
   ```python
   raw_port = os.getenv("SMTP_PORT")
   SMTP_PORT = int(raw_port) if raw_port and raw_port.isdigit() else (465 if SMTP_USE_TLS else 587)
   ```
3. **Clean Up Database Models**: Remove legacy schemas (`ScanSource`, `ScanJob`, `ImportCandidate`, `RedirectSlug`, and `Collection/CollectionItem`) if they are out of scope for the current MVP, or document them as planned features in a roadmap.
4. **Complete or Remove Post Activities**: Decide whether to roll out the Post Activities feature. If rolling out, remove the hardcoded overwrites in the backend post router and expose the fields in the Astro admin editor. If not, clean up the database columns and Pydantic schemas.
5. **Load Environment in Scripts**: Modify scripts to load `.env` if it exists:
   ```bash
   if [ -f .env ]; then
     export $(grep -v '^#' .env | xargs)
   fi
   ```
   And substitute `-U postgres` and database parameters with `${POSTGRES_USER:-postgres}` and `${POSTGRES_DB:-postmarked}`.
6. **Clean Up Unused Frontend Islands**: Delete or properly integrate components like `SearchIsland.jsx`, `TimelineIsland.jsx`, and `TripProgressIsland.jsx` to reduce client-side bundle size.
