# Trip Deletion and Service Worker Cache Fix — 2026-05-16

## Problem

Two related issues reported:

1. **Orphaned stops after trip deletion** — Deleting a trip from the Trips Admin page removed the trip record, but associated stops and planned stops remained in the database and continued to appear on the Stops admin page.

2. **Admin and public frontend out of sync** — After deleting a trip, the admin page correctly reflected the deletion, but the public-facing trips page (`/trips`) still showed the deleted trip.

## Root Causes

### Orphaned stops

The SQLAlchemy `Trip.stops` relationship had `cascade="all, delete-orphan"` defined, and the database FK `stop.trip_id` had `ondelete="CASCADE"`. However, with async SQLAlchemy, `session.delete(trip)` does not always cascade properly because the child collections may not be loaded into the session before the delete is issued. The `Trip.planned_stops` relationship had **no cascade** at all.

### Public page showing stale data

The service worker (`web/public/sw.js`) used a **stale-while-revalidate** strategy for all GET requests to non-admin paths. This meant the rendered HTML of `/trips` was cached and served immediately, with a background fetch updating the cache. Admin pages were excluded from caching, so they always showed fresh data — hence the mismatch.

## Changes

### 1. `api/app/routers/admin/trips.py`

Added explicit deletion of child records before deleting the trip:

- Added `delete` to the SQLAlchemy imports
- Added `Stop` and `PlannedStop` to model imports
- In `delete_trip_admin()`, added two `session.execute(delete(...))` calls that remove all stops and planned stops for the trip before deleting the trip itself

This ensures orphaned records are never left behind, regardless of whether the database-level cascade or ORM cascade fires.

### 2. `api/app/models/content.py`

Added `cascade="all, delete-orphan"` to the `Trip.planned_stops` relationship (line 105) for consistency with the existing `stops` relationship. This provides ORM-level cascade as a safety net alongside the explicit deletes in the API.

### 3. `web/public/sw.js`

Restructured the service worker to only cache static assets (CSS, JS, images, fonts, PMTiles), not HTML pages:

- Removed the broad "stale-while-revalidate for all non-admin GET requests" behavior
- Added a regex check so only known static asset extensions are cached (`.css`, `.js`, `.png`, `.jpg`, `.svg`, `.ico`, `.woff2`, `.woff`, `.ttf`, `.pmtiles`)
- Removed `/` from the precache list (HTML pages should not be precached)
- Bumped `CACHE_NAME` from `goodpath-cache-v1` to `goodpath-cache-v2` so the existing stale cache is invalidated on the next service worker activation

This ensures HTML pages always load fresh from the network while preserving offline support for static assets.

## Files Modified

| File | Change |
|------|--------|
| `api/app/routers/admin/trips.py` | Explicit stop/planned_stop deletion on trip delete |
| `api/app/models/content.py` | Added cascade to `planned_stops` relationship |
| `web/public/sw.js` | Cache only static assets; bumped cache version |

## How to Verify

1. Create a trip with stops via the admin panel.
2. Delete the trip from the Trips Admin page.
3. Confirm the trip no longer appears on the Stops admin page.
4. Confirm the trip no longer appears on the public `/trips` page (hard refresh if needed for service worker update).
