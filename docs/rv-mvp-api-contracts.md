# RV MVP API Contracts

Status: current public reader contract  
Last updated: 2026-05-04

These endpoints support the RV-specific reader experience: current location, recent updates, continuous timeline, and trip segment progress.

Public endpoints intentionally omit private RV fields such as reservation numbers, site numbers, private notes, costs, fuel data, private comments, and private contact details.

## `GET /api/home`

Purpose: render the family home page.

Returns:

- `journey`: active continuous journey summary.
- `current_stop`: where the RV is now.
- `next_stop`: next visible lived stop, when available.
- `recent_stops`: recent visible lived stops.
- `recent_posts`: recent visible journal updates.
- `active_trip_segment`: current trip/chapter summary.
- `upcoming_planned_stops`: public-safe planned stops from RV Trip Wizard imports.

Use this for:

- Home page current-location panel.
- Recent updates feed.
- Next-stop preview.
- Map preview markers.
- "Up next" planned route hints.

## `GET /api/timeline`

Purpose: render the continuous RV life timeline.

Query parameters:

- `limit`: page size.
- `offset`: pagination offset.
- `trip_slug`: optional trip segment filter.

Returns:

- `journey`
- `updates`: unified chronological feed
- `limit`
- `offset`
- `has_more`

Each update has:

- `kind`: `post` or `stop`
- shared display fields such as `id`, `title`, `posted_at`, optional trip/stop handles, and optional media
- post-specific fields such as `body`
- stop-specific fields such as `place_name`, `stop_type`, and `cover_media`

Use this for:

- Full timeline page.
- Recent movement summary.
- Continuous journey browsing.

## `GET /api/trip-segments`

Purpose: list visible trip segments inside the continuous journey.

Returns trip segment summaries:

- `id`
- `slug`
- `title`
- `summary`
- `start_date`
- `end_date`
- `status`
- `total_distance_meters`
- `stops_completed`
- `stops_total`

Use this for:

- Trip/chapter index.
- Public navigation into trip progress pages.

## `GET /api/trip-segments/{slug}`

Purpose: render a trip segment detail/progress page.

Returns:

- trip segment summary/detail fields.
- ordered visible stops with coordinates.
- posts attached to the segment.

Use this for:

- Trip segment hero and mini-map.
- Ordered stop list.
- Future synchronized map/timeline/photo scrubber.
- Stop drill-in entry points.

## `GET /api/trips/{trip_slug}/stops/{stop_slug}`

Purpose: render one public stop detail page.

Returns:

- stop summary fields.
- `body`
- `trip_slug`
- `trip_title`
- attached visible media.
- posts attached to the stop.
- previous/next stop siblings.

Use this for:

- Stop detail page.
- Stop comments.
- Stop gallery.
- Prev/next route navigation.

## Public Stop Fields

Public stop summaries include:

- title, slug, summary
- public place/address label
- date range and nights
- status and stop type
- latitude and longitude
- RV feature chips
- miles from previous stop
- estimated travel time
- public note
- public cover media if available

They do not include:

- reservation data
- site number
- private notes
- private RV Trip Wizard comments
- fuel data
- cost data
