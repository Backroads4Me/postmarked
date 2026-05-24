# API Contracts

Status: current public reader contract
Last updated: 2026-05-23

Public endpoints omit private fields such as reservation numbers, site numbers, private notes, costs, and fuel data.

## `GET /api/home`

Purpose: render the home page.

Returns:

- `current_stop`: where the traveler is now.
- `next_stop`: next visible stop, when available.
- `previous_stop`: previous stop, when available.
- `recent_stops`: recent visible stops.
- `recent_posts`: recent visible journal updates.
- `active_trip_segment`: current trip/chapter summary.
- `upcoming_stops`: future published stops.

Use this for:

- Home page current-location panel.
- Recent updates feed.
- Next/previous stop navigation on the current location card.
- "Up next" published route hints.

## `GET /api/timeline`

Purpose: render the chronological timeline.

Query parameters:

- `limit`: page size.
- `offset`: pagination offset.
- `trip_slug`: optional trip segment filter.

Returns:

- `updates`: unified chronological feed of posts and stops.
- `limit`, `offset`, `has_more`

Each update has:

- `kind`: `post` or `stop`
- shared display fields: `id`, `title`, `posted_at`, optional trip/stop handles, optional media
- post-specific: `body`
- stop-specific: `place_name`, `cover_media`

## `GET /api/trip-segments`

Purpose: list visible trip segments.

Returns trip segment summaries:

- `id`, `slug`, `title`, `summary`
- `start_date`, `end_date`, `status`
- `total_distance_meters`, `stops_completed`, `stops_total`

## `GET /api/trip-segments/{slug}`

Purpose: render a trip segment detail page.

Returns:

- Trip segment summary/detail fields.
- Ordered visible stops with coordinates.
- Posts attached to the segment.

## `GET /api/trips/{trip_slug}/stops/{stop_slug}`

Purpose: render one public stop detail page.

Returns:

- Stop summary fields, `body`, `trip_slug`, `trip_title`.
- Attached visible media.
- Posts attached to the stop.
- Previous/next stop siblings (`prev`, `next`).

## Public Stop Fields

Included:

- title, slug, summary
- public place/address label
- date range and nights
- status
- latitude and longitude
- feature chips
- miles from previous stop
- estimated travel time
- public note
- public cover media

Excluded:

- reservation data, site number
- private notes and comments
- phone, email
- costs and fuel details
- exact future location for private trips
