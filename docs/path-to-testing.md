# Postmarked Testing Checklist

Status: ready for beta testing
Last updated: 2026-05-24

## What Is Ready

- Docker Compose dev stack.
- Automatic Alembic migration on compose startup.
- Seeded demo data (trips, stops, recent posts).
- Public home, timeline, trips index, trip segment detail, stop detail, and post detail pages.
- Breadcrumb navigation across all detail pages.
- Current location card with trip context and prev/next stop navigation.
- Admin dashboard.
- Current stop picker.
- Manual stop management.
- Quick post composer with photo attachment.
- Activity posts with optional Google Maps POI enrichment.
- Pending user approval page.
- RV Trip Wizard Excel preview/apply flow.
- Media streaming through `/media/{asset_id}/{variant}`.
- Google Maps provider with route schematic fallback when no API key is configured.
- Weather display on current location card.

## Verified Checks

These checks passed on 2026-05-04:

```bash
docker compose ps
docker exec api alembic current
docker exec api python -c "import app.main; print('api import ok')"
docker exec api python scripts/seed.py
docker exec web npm run build
```

Verified API/page behavior:

- `/api/health/ready` returns `200`.
- `/api/home` returns the active journey, current stop, next/previous stops, recent posts, recent stops, active trip segment, and upcoming published stops.
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
   - where you are now
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
- Password: `changeme`

## Ready For Beta Testing?

Yes, with caveats. The app is suitable for beta testers once deployed. Do not treat the local seeded password or default Flower auth as production-safe — change both before any real deployment.

## Non-Blocking Polish Backlog

Highest value before wider family testing:

1. Self-host fonts instead of loading Google Fonts.
2. Replace rough emoji/iconography with consistent line icons.
3. Add friendly SSR error banners where pages currently degrade quietly.
4. Verify public and admin pages at 390px and 1280px widths.
5. Add auth-aware header state with login/logout/admin affordances.
6. Add admin settings/profile pages for traveler details.
7. Add deeper tests for import reimport edge cases.
8. Add deeper tests for visibility inheritance across journey, trip, stop, post, and media.
9. Finish production reverse-proxy/TLS/header review before deploying on a public domain.
