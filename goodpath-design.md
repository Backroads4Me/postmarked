# Goodpath — Design Spec

**Status:** Approved for implementation planning
**Date:** 2026-04-06

This document is the single, self-contained source of truth for what Goodpath V1 is. It is the only product specification — there is no companion requirements document, and no prior document is binding.

---

## 1. Purpose and Scope

Goodpath is a self-hosted, media-rich, RV-specific travel journal for one publisher and a small invited audience. It exists to let an RV traveler publish trips, stops, photos, videos, an RV profile, and an about-the-travelers profile, and to let friends and family follow along on a polished mobile-first reader with a synchronized map / timeline / media experience.

The center of the product is `Trip → Stop → Media`, with `Timeline`, `Places`, and `Collections` as alternate browsing layers over the same content.

V1 explicitly excludes: multi-author publishing, native mobile apps, cloud object storage requirements, real-time chat, social-graph following, AI captioning, facial recognition, third-party API, and collaborative trip editing.

### 1.1 Product principles

- **RV-first storytelling.** The core unit is an RV journey made of real travel stops and route progress, not a generic trip log.
- **Map-first storytelling.** Location is a primary organizing concept, not metadata.
- **Timeline-first followability.** Readers should always be able to understand where the rig has been and what happened at each stop.
- **Scan-first media workflow.** Filesystem ingestion is a first-class capability, not an afterthought.
- **Manual curation where it matters.** Trips, stops, captions, featured media, summaries, and visibility are owner-controlled.
- **Fast browsing over perfect metadata.** The system stays useful even when EXIF is incomplete.
- **Mobile readers first.** The public reader is designed for phones from the start.
- **Private by design.** Self-hosted deployment, audience control, and authenticated media streaming are core, not add-ons.
- **Long-term ownership.** Local storage, exportable data, and a clean backup story protect memories indefinitely.

### 1.2 Target users

- **Owner / publisher.** One primary admin account. Maintains trips, stops, routes, media, the RV profile, the traveler profile, visibility, readers, and site settings. Wants both fast publishing and deeper curation.
- **Approved reader.** Friends or family with approved accounts. Can view all content the owner allows, including private content. Can comment, like, and subscribe to notifications.
- **Pending user.** Has registered but is not yet approved. Can authenticate, but sees only public content until approved.
- **Anonymous visitor.** Sees only public content. May open shared trip links without registering.

### 1.3 Success criteria

- A new trip can be created and published with stops, coordinates, photos, and captions in under fifteen minutes.
- A friend opening a shared trip on a phone in a national park with weak LTE can browse the map, timeline, and media without confusion or excessive load times.
- Photo and video ingestion remains reliable for large batches and does not require manual per-file organization.
- Private content is consistently invisible to anonymous and unapproved visitors — including titles, slugs, coordinates, thumbnails, and counts.

---

## 2. Architecture

### 2.1 Stack (locked)

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 + GeoAlchemy2, Alembic migrations, Pydantic v2.
- **Database:** PostgreSQL 16 with PostGIS 3.
- **Background jobs:** Celery 5 with Redis broker. Celery Beat for scheduled jobs. Flower for admin-only job inspection.
- **Cache / broker:** Redis 7.
- **Frontend:** Astro 4 with React islands, Tailwind CSS, shadcn/ui component primitives, Framer Motion, View Transitions API. PWA via `@vite-pwa/astro`.
- **Map:** MapLibre GL JS in the browser; self-hosted vector tiles via Protomaps PMTiles served by Caddy as static range-request files. Outbound POI links use Google Maps URL schemes (no API key required).
- **Auth:** `fastapi-users` for sessions, password reset, and email verification; Authlib for Google OAuth. HTTP-only secure cookies on the shared domain.
- **Reverse proxy:** Caddy 2 with automatic HTTPS.
- **Deployment:** Docker Compose on a single Linux host.

### 2.2 Service topology

| Service  | Image basis            | Purpose                                                      |
| -------- | ---------------------- | ------------------------------------------------------------ |
| `proxy`  | `caddy:2`              | TLS termination, routing, static PMTiles serving, rate limiting |
| `web`    | Custom Node 22         | Astro SSR + static                                           |
| `api`    | Custom Python 3.12     | FastAPI / Uvicorn                                            |
| `worker` | Custom Python 3.12     | Celery worker                                                |
| `beat`   | Custom Python 3.12     | Celery beat scheduler                                        |
| `flower` | `mher/flower`          | Celery monitoring (admin-only, behind auth)                  |
| `db`     | `postgis/postgis:16-3` | PostgreSQL + PostGIS                                         |
| `redis`  | `redis:7-alpine`       | Broker + cache                                               |

### 2.3 Volumes

- `db_data` — Postgres data
- `originals` — uploaded original media (never web-served directly)
- `derivatives` — generated thumbnails, AVIF/WebP/JPEG renditions, video posters (regeneratable)
- `pmtiles` — vector tile archives
- `backups` — Postgres dumps and originals snapshots

### 2.4 Routing (Caddy)

- `https://example.com/` → `web`
- `https://example.com/api/*` → `api`
- `https://example.com/tiles/*.pmtiles` → static file with range support
- `https://example.com/media/*` → `api` (authenticated streaming endpoint)
- `https://admin.example.com/flower/*` → `flower` (basic-auth-gated)

### 2.5 Repository layout

```text
goodpath/
  compose/
    docker-compose.yml
    docker-compose.dev.yml
  caddy/
    Caddyfile
  api/
    pyproject.toml
    alembic/
    app/
      main.py
      config.py
      db.py
      models/
      schemas/
      routers/
      services/
      tasks/                # Celery tasks
      auth/
      media/
      maps/
      imports/
  web/
    package.json
    astro.config.mjs
    tailwind.config.ts
    src/
      pages/                # Astro routes (public + admin)
      components/           # React islands + Astro components
      layouts/
      lib/                  # API client, auth helpers
      styles/
  pmtiles/
  scripts/
    backup.sh
    restore.sh
    regenerate-derivatives.sh
  docs/
```

---

## 3. Domain Model

### 3.1 Enums

```python
class Visibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"

class TripStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class StopStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class StopType(str, Enum):
    CAMPGROUND = "campground"
    BOONDOCKING = "boondocking"
    OVERNIGHT = "overnight"
    ATTRACTION = "attraction"
    RESTAURANT = "restaurant"
    SERVICE = "service"
    OTHER = "other"

class MediaKind(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"

class MediaProcessingState(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class NotificationFrequency(str, Enum):
    ALL_UPDATES = "all_updates"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"
    MONTHLY_DIGEST = "monthly_digest"
    NONE = "none"

class POIType(str, Enum):
    CAMPGROUND = "campground"
    TRAILHEAD = "trailhead"
    FUEL = "fuel"
    RESTAURANT = "restaurant"
    ATTRACTION = "attraction"
    OTHER = "other"
```

### 3.2 Core entities

**User**
- `id`, `email` (unique), `password_hash` (nullable for OAuth-only), `display_name`, `avatar_path`
- `role: UserRole`, `approval_state: ApprovalState`
- `email_verified_at`, `created_at`, `updated_at`
- Relations: `notification_preference`, `comments`, `likes`

**NotificationPreference** (1:1 with User)
- `frequency: NotificationFrequency`
- `unsubscribed_token` (random, used for one-click unsubscribe links)

**Trip**
- `id`, `slug` (unique, immutable after first publish; old slugs preserved as redirects), `title`, `summary`, `body` (markdown, optional)
- `start_date`, `end_date` (nullable)
- `status: TripStatus`, `visibility: Visibility`
- `cover_media_id` (FK MediaAsset, nullable)
- `cover_bounds` (PostGIS `geography(POLYGON)`, auto-computed from stops with 10% padding, manually overridable)
- `route_track` (PostGIS `geography(LINESTRING)`, nullable, populated by GPX import)
- `total_distance_meters` (computed; sum of geodesic legs between stops in route order, overridden by `ST_Length(route_track)` when present)
- `tags: ARRAY(TEXT)` (simple owner-managed labels; no separate tag entity in V1)
- `published_at`, `created_at`, `updated_at`
- Relations: `stops` (ordered), `pois` (via stops), `media`

**Stop**
- `id`, `trip_id` (FK), `slug` (unique within trip)
- `title`, `summary`, `body` (markdown)
- `location: geography(POINT, 4326)` — required
- `place_name`, `address_label` (optional human-readable)
- `start_date` (required), `end_date` (nullable)
- `sort_order` (integer, canonical route order — usually but not necessarily chronological)
- `status: StopStatus`, `stop_type: StopType`, `visibility: Visibility`
- `is_favorite: bool` (powers a "Favorites" auto-collection later)
- `tags: ARRAY(TEXT)`
- `cover_media_id` (FK MediaAsset, nullable)
- `published_at`, `created_at`, `updated_at`
- Relations: `media`, `pois`, `comments`

**PointOfInterest**
- `id`, `stop_id` (FK), `label`, `poi_type: POIType`, `notes` (optional), `google_maps_url`
- `location: geography(POINT, 4326)`
- `created_at`, `updated_at`

**MediaAsset** (unified photo + video)
- `id`, `kind: MediaKind`, `processing_state: MediaProcessingState`, `error_message` (nullable)
- `original_path` (relative to `originals` volume), `original_sha256` (unique — V1 dedup key), `original_filename`, `original_size_bytes`, `mime_type`
- `width`, `height`, `aspect_ratio`, `duration_seconds` (video), `dominant_color` (hex), `blurhash`
- `taken_at` (from EXIF when present), `gps_location: geography(POINT, 4326)` (nullable)
- `caption`, `alt_text`, `visibility: Visibility`
- `derivative_paths: JSONB` — `{ "thumb": "...", "display_avif": "...", "display_webp": "...", "display_jpeg": "...", "video_poster": "..." }`
- `trip_id` (nullable — set during intake before stop assignment)
- `stop_id` (nullable — at most one stop per asset in V1)
- `attached_to` (`'rv_profile' | 'traveler_profile' | null`) — used only for singleton-profile galleries
- `featured: bool`, `sort_order` (within stop)
- `created_at`, `updated_at`
- **Effective visibility rule:** `min(self.visibility, parent.visibility)` where parent is the stop (if assigned) or trip (otherwise). A public photo on a private stop is private.

**RvProfile** (singleton)
- `id` (always 1), `visibility`
- `title`, `rv_name`, `make`, `model`, `year`, `rv_type`, `length_feet`
- `description` (markdown), `setup_notes` (markdown), `towing_info` (markdown), `modifications` (markdown)
- `cover_media_id`
- `created_at`, `updated_at`
- Gallery: `MediaAsset` rows with `attached_to: enum('rv_profile', 'traveler_profile', null)` set to `'rv_profile'`. Avoids overloading `stop_id` / `trip_id`.

**TravelerProfile** (singleton)
- `id` (always 1), `visibility`
- `title`, `intro` (markdown), `story` (markdown), `travel_style` (markdown), `family_info` (markdown), `pet_info` (markdown), `contact_links: JSONB`
- `cover_media_id`
- `created_at`, `updated_at`
- Gallery: `MediaAsset` rows with `attached_to = 'traveler_profile'`.

**Comment**
- `id`, `author_id` (FK User; commenting requires APPROVED + email-verified)
- `target_kind: enum('stop', 'media')`, `target_id`
- `body` (markdown, length-limited, sanitized)
- `created_at`, `updated_at`, `deleted_at` (soft delete by admin moderation)

**Like**
- `id`, `author_id`, `target_kind`, `target_id`, `created_at`
- Unique on (`author_id`, `target_kind`, `target_id`)

**Collection**
- `id`, `slug`, `title`, `summary`, `cover_media_id`, `visibility`, `sort_order`, `created_at`, `updated_at`

**CollectionItem**
- `collection_id`, `media_id`, `sort_order`

**ScanSource**
- `id`, `label`, `root_path` (relative to a configured base inside the originals volume), `enabled: bool`, `interval_minutes`
- `last_run_at`, `last_status`

**ScanJob**
- `id`, `scan_source_id`, `status` (queued/running/completed/failed), `started_at`, `finished_at`, `files_seen`, `files_new`, `files_failed`, `error_message`

**ImportCandidate**
- `id`, `scan_job_id`, `path`, `sha256`, `status` (new/duplicate/imported/skipped/failed)
- `exif_taken_at`, `exif_gps`, `suggested_stop_id` (nullable, derived from EXIF GPS proximity to existing stops)

**NotificationLog**
- `id`, `user_id`, `kind`, `payload: JSONB`, `sent_at`, `delivery_status`, `error_message`

**RedirectSlug**
- `id`, `entity_kind` (`trip` or `stop`), `entity_id`, `old_slug`, `created_at`
- Whenever a trip or stop slug is changed, the previous slug is recorded here. The public route resolver checks `RedirectSlug` on miss and issues a 301 to the current canonical URL. Prevents broken shared links.

**AuditLog**
- `id`, `actor_id`, `action`, `target_kind`, `target_id`, `payload: JSONB`, `created_at`

### 3.3 Cardinality rules

- A trip has many stops; a stop belongs to exactly one trip.
- A media asset belongs to at most one stop in V1. It may be unassigned (intake) or attached to a singleton profile.
- A comment targets a stop or a media asset.
- A like targets a stop or a media asset.
- The RV profile and traveler profile are singletons; multi-rig history is out of scope for V1.

---

## 4. Visibility and Authorization

### 4.1 Visibility resolution

`effective_visibility(asset) = min(asset.visibility, parent.visibility)` where `min(PUBLIC, PRIVATE) = PRIVATE`. Trips have no parent. Stops inherit from their trip. Media inherits from its stop (or trip if intake).

### 4.2 Reader access matrix

| Reader               | PUBLIC | PRIVATE | Admin tools |
| -------------------- | ------ | ------- | ----------- |
| Anonymous            | ✅      | ❌       | ❌           |
| Pending              | ✅      | ❌       | ❌           |
| Approved             | ✅      | ✅       | ❌           |
| Admin                | ✅      | ✅       | ✅           |

The system must never leak private titles, slugs, coordinates, thumbnails, counts, or search results to unauthorized viewers. Every list endpoint applies visibility filtering at the SQL layer, not in the response serializer.

### 4.3 Media streaming

All media — public and private — is served by a single authenticated FastAPI streaming endpoint at `/media/{asset_id}/{variant}`. The endpoint:

- Looks up the asset and its effective visibility.
- Rejects unauthorized requests with 404 (not 403, to avoid existence disclosure).
- Streams from the `originals` or `derivatives` volume with `Range` support.
- Emits `ETag` (= asset id + variant + updated_at hash) and `Cache-Control: private, max-age=86400` for authorized clients.
- Originals live outside any web-served directory; there is no static fallback.

---

## 5. Authentication and Accounts

- Email + password registration with mandatory email verification before approval.
- Google OAuth via Authlib.
- Password reset via emailed token.
- Sessions are HTTP-only secure cookies, `SameSite=Lax`, signed.
- `ApprovalState` defaults to `PENDING` on registration. Admin must approve from `/admin/users`.
- Registration globally enable/disable-able (covers both credential and OAuth signups).
- Roles: `ADMIN`, `USER`. One primary admin assumed; multiple admins allowed technically.
- Pending users see exactly what anonymous users see.
- Account profile page (`/profile`) shows account details, approval state, notification preferences, and account actions (password change, delete account).

---

## 6. Content Workflows

### 6.1 Owner publishes a new completed trip

Create trip (status `PLANNED` or `COMPLETED`) → add stops via map click or form → upload or assign media to stops → write stop summaries and bodies → optionally import GPX → publish trip (status `PUBLISHED`, `published_at = now`) → notification fan-out.

### 6.2 Owner plans a future trip

Create trip with `status = PLANNED` → add intended stops with `status = PLANNED` → reorder by drag → attach POIs and notes → leave media empty → later flip status to `ACTIVE` then `COMPLETED` → publish.

### 6.3 Owner bulk-imports media

Configure scan source → manual or scheduled scan → scanner walks paths, computes SHA-256, parses EXIF, generates blurhash + thumbnails → results land in `/admin/intake` → owner assigns to stops in batch, optionally creating new stops from EXIF GPS clusters.

### 6.4 Reader follows a trip on mobile

Open shared link → trip overview at-a-glance (above the fold: hero, mini-map, dates, counts, current status) → tap into synchronized map/timeline/media view → tap a stop → read summary, swipe through media in lightbox → navigate prev/next stop via swipe or buttons → optionally comment if approved.

### 6.5 Reader learns about the RV

Top-nav "RV" link → cover, gallery, description, specs, towing, mods → links back into trips.

### 6.6 Reader learns about the travelers

Top-nav "About" link → cover, story, travel style, optional family/pets/contact → links back into trips.

---

## 7. Media Pipeline

### 7.1 Supported formats

- **Photos in:** JPEG, PNG, WebP, AVIF, HEIC/HEIF
- **Videos in:** MP4 (H.264/H.265), MOV
- **Photos out:** original preserved + AVIF + WebP + JPEG fallbacks at multiple sizes (thumb, display)
- **Videos out:** original streamed via Range; JPEG poster generated from first non-black frame; web-optimized H.264 transcode is **P2** (not V1).

### 7.2 Upload paths

- **Direct browser upload:** TUS protocol for *all* media (photos and videos), supporting resumable uploads over flaky campground wifi. Multi-file selection in one action. Drag-and-drop.
- **Filesystem scan:** see §6.3.

### 7.3 Processing

- All processing runs in Celery workers, asynchronous, retryable, per-asset state visible in `/admin/intake` and `/admin/jobs`.
- Pipeline stages per asset: extract metadata → compute SHA-256 → dedup check → extract EXIF (Pillow + pyexiv2) → orient correctly → generate thumbnails → generate display variants (AVIF/WebP/JPEG via Pillow + pillow-heif + pillow-avif-plugin) → compute blurhash + dominant color → for video, ffmpeg poster extraction → mark `READY` or `FAILED`.
- Failures store `error_message` and remain retryable from admin.
- Originals are immutable. Re-processing regenerates derivatives only.

### 7.4 Dedup

- Exact dedup key: `original_sha256`. Re-uploads or re-scans of the same bytes are skipped and surfaced as duplicates in admin.
- Near-duplicate hint: matching EXIF `DateTimeOriginal` ± 2 seconds AND GPS within 5 meters. Surfaced in admin only; not auto-deduped.

---

## 8. Map, Timeline, and Synchronized Browsing

### 8.1 Map rendering

- MapLibre GL JS in a React island.
- Vector tiles from a self-hosted PMTiles file served by Caddy with Range support.
- Marker layer for stops; clustered via `supercluster` on the client when > 50 visible.
- Route line layer rendered from `Trip.route_track` when present; otherwise rendered as straight geodesic segments between consecutive stops in `sort_order`.
- POI markers shown when zoomed into a single stop's neighborhood; tapping a POI opens its `google_maps_url` in a new tab.
- Mobile: marker hit targets ≥ 44 px; popovers anchored to the bottom sheet, not overlaying the map center.

### 8.2 Synchronized view state

- The map / timeline / media view is fully URL-driven:
  `?trip=<slug>&stop=<slug>&media=<id>&view=map|timeline|grid`
- All three panels read from URL state; user interactions push history entries via `pushState` or View Transitions.
- Back button always works. Sharing the URL reproduces the exact pane configuration.

### 8.3 Timeline

- Desktop: vertical timeline rail on the left, stops grouped by trip with media counts and dates.
- Mobile: horizontal scrubbable strip pinned to the bottom of the map view; tap a tick to jump to that stop.

### 8.4 Lightbox

- Full-screen overlay React island.
- Keyboard: ←/→ navigate, Esc close, Space play/pause for video.
- Mobile: swipe left/right navigate, swipe down close, pinch zoom for photos.
- Caption + alt text + EXIF date displayed; comments accessible via a sheet without leaving the lightbox.

---

## 9. Public Pages

All public pages are Astro routes. Static or SSR per page based on personalization needs. React islands only where interaction requires it.

### 9.1 Home (`/`)

- Hero block with featured/cover media.
- **"Where the rig is now" widget**: for any trip with `status = ACTIVE`, show the most recent published stop with a small map and date. This is the V1 differentiator.
- Recent updates section (newest first).
- Entry points: Trips, Map, Timeline, RV, About.

### 9.2 Trips index (`/trips`)

- Cards with cover, title, date range, summary, stop count, photo count.
- Default sort: newest first by `start_date` desc; active trips pinned to the top.
- Filter by year, status, tag.

### 9.3 Trip detail (`/trips/{slug}`)

- **Hero must show, above the fold on mobile, with no scrolling required:** hero image, route mini-map, date range, stop count, photo count, total distance, current status.
- Optional long-form trip body (markdown) rendered below the hero when present.
- Stop list in canonical route order (manual `sort_order`); user can re-sort by date.
- Mini-timeline.
- Synchronized map/timeline/media link.
- Comments live on stops and media in V1; the trip page itself does not host a comment thread.

### 9.4 Stop detail (`/trips/{trip_slug}/stops/{stop_slug}`)

- Title, dates, location, body (markdown), media gallery, POI list with outbound Google Maps links.
- Comments section (flat, newest first by default, oldest-first option).
- Likes.
- **Prev/next stop navigation within the trip**, both as on-page buttons and via swipe gesture on mobile.

### 9.5 Map view (`/map`)

- Full-bleed MapLibre map.
- All visible (per visibility rules) stops as markers.
- Trip filter, year filter, route line toggle.
- Synchronized with timeline and media panels (see §8.2).

### 9.6 Timeline view (`/timeline`)

- All media grouped by day, newest first.
- Filter by trip, year, media type.
- Tapping a media item opens the lightbox; nearby items navigate via swipe.
- Virtualized rendering for any view exceeding 200 items.

### 9.7 Places view (`/places`)

- Map-driven cluster view of all stops (V1 definition: a "place" *is* a stop).
- Tapping a cluster zooms; tapping a marker opens the stop.
- Reverse-geocoded place names are P3.

### 9.8 Collections (`/collections`, `/collections/{slug}`)

- Curated owner-defined collections of media spanning multiple trips.
- Index page: cards with cover, title, count.
- Detail page: virtualized photo grid.

### 9.9 RV profile (`/rv`)

- Cover, gallery, description, specs (make, model, year, type, length), setup notes, towing info, modifications.
- Visibility-aware.

### 9.10 About (`/about`)

- Cover, intro, story, travel style, optional family / pet info, contact links.
- Visibility-aware.

### 9.11 Profile (`/profile`)

- Account details, approval state, notification preferences (one-tap toggles), password change, delete account.

### 9.12 Auth (`/auth/login`, `/auth/register`, `/auth/verify`, `/auth/reset`)

- Standard flows. All form pages must be fully mobile-usable.

### 9.13 Mobile navigation

- **Mobile (< 768 px):** bottom tab bar — Home / Trips / Map / Timeline / About. Hamburger menus are not used.
- **Desktop:** top nav with the same destinations + RV link.

### 9.14 Default ordering

- **Within a single trip:** stops display in manual `sort_order` (canonical) with a user option to sort by date.
- **Everywhere else** (trips index, timeline, places, home recent, comments, collections, all-photos galleries): default sort is **newest first** with user-selectable alternates.

---

## 10. Admin Pages

All admin pages live under `/admin/*`, gated by `role = ADMIN`. Bottom nav is replaced by a sidebar on desktop and a top app bar on mobile.

- `/admin` — dashboard: scan status, processing failures, pending users, recent comments
- `/admin/trips` — list, create, edit, delete; trip-builder includes the map-driven stop sequence editor
- `/admin/trips/{id}/stops` — drag-to-reorder, map-click-to-add stops, inline edit
- `/admin/stops/{id}` — full stop editor with markdown body, media attachment, POI manager
- `/admin/intake` — scan + upload intake queue, batch assignment to stops, dedup hints, processing state per asset
- `/admin/scan-sources` — configure scan paths, intervals, manual run
- `/admin/media/{id}` — single-asset editor (caption, alt, visibility, taken_at override, retry processing)
- `/admin/collections` — collection CRUD, drag-to-order items
- `/admin/rv` — RV profile editor
- `/admin/about` — traveler profile editor
- `/admin/users` — list, approve, reject, change role, search
- `/admin/comments` — moderation queue, soft-delete, restore
- `/admin/settings` — site title, registration toggle, SMTP overrides, default visibility
- `/admin/jobs` — Celery job inspection (recent jobs, retries, failures, one-click retry)
- `/admin/audit` — audit log viewer

### 10.1 Admin trip-builder map workflow

- Click anywhere on the map to add a stop (location prefilled, form opens in side panel).
- Drag a stop marker to reposition (location updates in form).
- Drag stops in the side list to reorder.
- Shift-click to add a POI to the nearest stop.
- POIs are draggable to reposition.
- "Preview route" toggles the route line.

---

## 11. Social Features

### 11.1 Comments

- **Approved + email-verified users only.** Anonymous reading is supported; anonymous commenting is not. (Resolves the §5/§9.10 contradiction in `requirements.md`.)
- Targets: stops, media. Not trips, not collections, in V1.
- Flat, no threading. Hard decision.
- Markdown body, length-limited (2000 chars), sanitized server-side.
- Soft-deleted by admin moderation.
- Default sort: newest first. Oldest-first optional.

### 11.2 Likes

- Approved users only for the action. Counts visible to all readers.
- Targets: stops, media.
- One like per (user, target). Toggle.

### 11.3 Notifications

- Per-user `NotificationFrequency`: `ALL_UPDATES`, `DAILY_DIGEST`, `WEEKLY_DIGEST`, `MONTHLY_DIGEST`, `NONE`.
- Triggered by trip publish, stop publish, media batch publish.
- Digests are idempotent: each digest window is bounded by `[last_sent_at, now]` and "since last sent" is the audit-of-record.
- Every email includes a one-click unsubscribe link backed by `NotificationPreference.unsubscribed_token`.
- Test-send endpoint for admin.
- Subscription is global (subscribe to *the publisher*); per-trip subscription is P3.
- Delivery failures logged in `NotificationLog`.

---

## 12. Search, Sort, Filter

- **Backend:** Postgres `tsvector` full-text search across trips, stops, collections, media captions/alt-text. No external search service in V1.
- **Filters:** year/date range, trip, visibility (admin only), media type, tags, place/country (when metadata exists).
- **Sort options:** newest first (default everywhere except within a single trip's stop list), oldest first, manual where relevant.

---

## 13. Performance Budget

- **Public trip detail page:** LCP < 2.5 s on a throttled mid-tier Android device over simulated 4G.
- **Lighthouse mobile performance score:** ≥ 90 on home, trips index, trip detail, stop detail, map (excluding tiles).
- Astro ships near-zero JS by default; React islands hydrate only on demand.
- Photo grids virtualize beyond 200 items.
- Map endpoints return simplified payloads for list/overview views.
- Image format negotiation: AVIF → WebP → JPEG via `<picture>`.
- Service worker caches the app shell + last-viewed trip data for offline-tolerant reading.

---

## 14. Security and Privacy

- Argon2id password hashing.
- HTTP-only secure cookies, `SameSite=Lax`, signed.
- CSRF tokens on all state-changing routes.
- CSP, HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.
- Rate limits on login, registration, password reset, comment submission, and the public media endpoint (per-IP and per-user where applicable).
- Signed `next` redirect parameter on auth flows (open-redirect prevention).
- Originals stored outside any web-served directory; served only via the authenticated streaming endpoint.
- 404 (not 403) for unauthorized access to private resources.
- Audit log entries for: user approval, role change, content publish, content delete, settings change.
- Reverse proxy and HTTPS expectations documented in deployment guide.

---

## 15. Accessibility

- Keyboard navigation for all major flows (browsing, lightbox, admin).
- Lightbox: keyboard close, prev/next, focus trap, focus restoration on close.
- Images carry alt text with sane fallbacks (filename or "Photo from {stop title}").
- Color contrast meets WCAG AA in both content and map overlays.
- Forms have visible labels and clear inline validation errors.
- Respects `prefers-reduced-motion` (View Transitions and Framer Motion fall back to instant transitions).

---

## 16. Deployment and Operations

### 16.1 Environment variables

- `DATABASE_URL`, `REDIS_URL`
- `SECRET_KEY`, `SESSION_COOKIE_DOMAIN`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
- `PUBLIC_BASE_URL`, `ALLOWED_HOSTS`
- `ORIGINALS_PATH`, `DERIVATIVES_PATH`, `PMTILES_PATH`
- `DIGEST_SECRET` (for cron-triggered digest endpoint)
- `FLOWER_BASIC_AUTH`

### 16.2 Health checks

- `GET /api/health` — liveness
- `GET /api/health/ready` — readiness (DB + Redis + storage volumes mounted)
- Caddy health probes both.

### 16.3 Cron / Beat schedule

- Scan sources fire on their per-source intervals.
- Daily digest: 09:00 in publisher's local time
- Weekly digest: Monday 09:00
- Monthly digest: 1st of month 09:00
- Audit-log retention: prune older than 365 days nightly

---

## 17. Backup and Restore

- `scripts/backup.sh` performs:
  - `pg_dump` of the database (compressed)
  - tar of the `originals` volume
  - copy of config files
  - writes to `backups` volume with timestamp
- The `derivatives` volume is **not** backed up (regeneratable via `scripts/regenerate-derivatives.sh` which enqueues Celery tasks for every `READY` asset).
- The `pmtiles` volume is **not** backed up (re-downloadable from Protomaps).
- `scripts/restore.sh` performs an atomic restore with sanity checks (Postgres restored to a temp DB, swapped on success).
- Backup and restore are documented in `docs/operations.md`.

---

## 18. V1 Scope: In and Out

### In V1

- Auth, approval workflow, email verification, Google OAuth
- Trip / Stop / RV profile / Traveler profile / POI / Collection CRUD
- Media upload (TUS resumable for all media), filesystem scan import, EXIF, HEIC, blurhash, dedup
- Visibility model with authenticated streaming
- Synchronized map / timeline / media browsing, URL-driven
- Self-hosted PMTiles + MapLibre + Google Maps deep links for POIs
- Modern mobile-first public reader, PWA with offline-tolerant shell
- Comments (flat), likes, notifications with digests
- Admin trip-builder, intake queue, jobs page, moderation, settings
- Postgres FTS search
- Backup / restore scripts, health checks, audit log
- GPX import (P2 within V1)

### Out of V1

- Multi-author publishing
- Native mobile apps
- Cloud object storage
- Real-time chat / DMs
- Social-graph following
- Per-trip notification subscriptions
- Comment threading
- Auto-generated / saved-filter collections
- Reverse-geocoded place gazetteer
- Real road-routed trip lines
- Multi-RV history
- Map provider abstraction
- Video web-optimized transcoding (poster only in V1)
- AI captioning
- Facial recognition
- Public REST/GraphQL API
- Third-party search backends

---

## 19. Resolved Open Questions (audit trail)

- **Map provider** → MapLibre + self-hosted PMTiles + Google Maps deep links for outbound POIs.
- **Stop body format** → Markdown.
- **Originals outside `public/`** → Yes, served only via authenticated streaming endpoint.
- **Email verification mandatory before approval** → Yes.
- **GPX import in V1** → Yes, P2.
- **Comments by anonymous guests** → No. Approved + email-verified users only.
- **Comment threading** → Flat only.
- **Visibility inheritance rule** → `min(self, parent)`.
- **Stop body field naming** → `summary` (short) + `body` (markdown long-form). `description` is dropped.
- **Multi-rig history** → Out of V1; singleton RV profile.
- **Route line for "continuous" trips** → Straight geodesic between stops, overridable by GPX.
- **Total trip distance** → Sum of geodesic legs, overridden by `ST_Length(route_track)` when present.
- **Trip cover bounds** → Auto from stop bbox + 10% padding, overridable.
- **Stop canonical order** → Manual `sort_order`, with date as a sort option.
- **Per-trip notification subscriptions** → Out of V1.
- **Search backend** → Postgres `tsvector`.
- **Dedup heuristic** → SHA-256 exact dedup; EXIF time + GPS as a near-duplicate hint only.
- **Scan schedule shape** → Per-source interval in minutes.
- **Auto-generated collections** → Out of V1.
- **`routeStyle` enum** → Removed; behavior derived from presence of `route_track` or stops.
- **Reverse-geocoded place entity** → Out of V1; "place" *is* a stop.
- **Mobile navigation** → Bottom tab bar; no hamburger.
- **Default sort everywhere outside a single trip** → Newest first.

---

## 20. What this spec deliberately does not cover

- **Visual design language.** Colors, typography, iconography, motion curves, component density, and lightbox visual treatment. Resolved in a follow-up frontend-design pass before implementation begins on the public reader.
- **Implementation sequencing.** Phase order, branch strategy, test strategy, CI. Resolved in an implementation plan written from this spec.

Goodpath is a greenfield project. No prior code, scaffold, or document is preserved or referenced.
