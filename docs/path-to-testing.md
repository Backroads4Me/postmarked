# Goodpath Testing Checklist

Status: local MVP ready for owner testing  
Last updated: 2026-05-04

This document replaces the old sprint tracker. S1-S3 stabilization work is complete; S4 polish remains open but is not blocking local testing.

## What Is Ready

- Docker Compose dev stack.
- Automatic Alembic migration on compose startup.
- Seeded full-time RV demo data.
- Public home, timeline, trips index, trip segment detail, and stop detail pages.
- Admin dashboard.
- Current stop picker.
- Manual stop management.
- Quick post composer with photo attachment.
- Journey management.
- Pending user approval page.
- RV Trip Wizard Excel preview/apply flow.
- Media streaming through `/media/{asset_id}/{variant}`.
- Google Maps provider with route schematic fallback when no API key is configured.
- Optional PMTiles map source when `PUBLIC_MAP_PROVIDER=maplibre`.

## Verified Checks

These checks passed on 2026-05-04:

```bash
docker compose --env-file .env -f compose/docker-compose.yml -f compose/docker-compose.dev.yml ps
docker exec compose-api-1 alembic current
docker exec compose-api-1 python -c "import app.main; print('api import ok')"
docker exec compose-api-1 python scripts/seed.py
docker exec compose-web-1 npm run build
```

Verified API/page behavior:

- `/api/health/ready` returns `200`.
- `/api/home` returns the active journey, current stop, recent posts, recent stops, active trip segment, and upcoming planned stops.
- `/api/timeline` returns a paginated unified feed of recent `post` and `stop` updates.
- `/api/trip-segments` returns visible trip segment summaries.
- `/api/trip-segments/michigan-ny-2026` returns ordered stops with coordinates.
- `/api/users/me` is mounted and returns `401` when unauthenticated.
- The rendered home page returns `200`.
- The active trip page returns `200`.
- `export-examples/trip-26-05-04-07-46.xlsx` parses as `Michigan, NY 2026` with 26 stops and no parser warnings.

## Owner Testing Path

Use http://localhost:4321 for normal testing.

1. Open `/`.
2. Confirm the home page quickly answers:
   - where the RV is now
   - what was shared recently
   - where the route is headed next
3. Open `/timeline`.
4. Open `/trips`.
5. Open `/trips/michigan-ny-2026`.
6. Open a stop detail from the trip page.
7. Log in at `/auth/login`.
8. Open `/admin`.
9. Mark a stop as current.
10. Create a quick post.
11. Manually add or edit a stop.
12. Import an RV Trip Wizard Excel export at `/admin/imports/rv-trip-wizard`.
13. Register a second test user and approve/reject them at `/admin/users`.

Admin credentials for local seed data:

- Email: `admin@example.com`
- Password: `admin123`

## Ready For Family Testing?

Start with owner testing first. After that, the app is suitable for one or two trusted family testers once obvious mobile and visual issues from the polish backlog are addressed.

Do not treat the local seeded password or default Flower auth as production-safe.

## Non-Blocking Polish Backlog

Highest value before wider family testing:

1. Self-host fonts instead of loading Google Fonts.
2. Replace rough emoji/iconography with consistent line icons.
3. Add friendly SSR error banners where pages currently degrade quietly.
4. Verify public and admin pages at 390px and 1280px widths.
5. Add auth-aware header state with login/logout/admin affordances.
6. Add `/rv` and `/about` public pages.
7. Add admin settings/profile pages for RV and traveler details.
8. Add deeper tests for import reimport edge cases.
9. Add deeper tests for visibility inheritance across journey, trip, stop, post, and media.
10. Finish production reverse-proxy/TLS/header review before deploying on a public domain.
