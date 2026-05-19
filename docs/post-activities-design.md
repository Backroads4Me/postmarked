# Post Activities Design

Status: proposed implementation design  
Last updated: 2026-05-16

## Decision

Postmarked should build local stop activities on top of posts instead of adding a separate `Activity` entity.

Posts already support the core activity needs:

- title and body text
- stop attachment
- photos and videos through media assets
- comments through `target_kind="post"`
- visibility controls
- timeline participation

The missing piece is richer semantics. A post should be able to represent either a quick road update or a local activity such as a hike, museum visit, restaurant night, attraction, service stop, or other experience that happened while staying at a stop.

## Goals

- Let the owner document what they did at each stop without creating another parallel content system.
- Keep quick posts fast and low-friction.
- Give activity posts enough structure to support filtering, richer stop pages, place cards, photos, comments, and optional Google Maps Place context.
- Preserve all existing posts and post APIs during rollout.
- Keep public reader responses privacy-safe through explicit allowlists.

## Data Model

### `Post`

Extend `Post` with optional activity-oriented fields:

- `post_type`: enum/string, default `update`.
  - `update`: current quick update behavior.
  - `activity`: a local activity or experience attached to a stop.
- `activity_type`: optional enum/string for activity posts.
  - Suggested values: `hiking`, `museum`, `restaurant`, `attraction`, `service`, `scenic_drive`, `shopping`, `family`, `other`.
- `summary`: optional short card/list text distinct from the long `body`.
- `activity_started_at`: optional datetime for when the activity happened.
- `activity_ended_at`: optional datetime for multi-hour or multi-day activities.
- `poi_id`: optional foreign key to `point_of_interest.id`.

Keep `posted_at` as the publish/timeline timestamp. For activity posts, sort by `activity_started_at` where the UI is specifically showing activities within a stop; fall back to `posted_at` when activity time is absent.

Existing posts should migrate to `post_type="update"` with all new fields null.

### `PointOfInterest`

Expand `PointOfInterest` into a reusable place record for a stop. It can be linked by one or more activity posts.

Recommended fields:

- Existing:
  - `stop_id`
  - `label`
  - `poi_type`
  - `notes`
  - `google_maps_url`
  - `location`
- Add:
  - `google_place_id`
  - `formatted_address`
  - `google_place_types`: array of strings
  - `website_url`
  - `phone`
  - `source`: `manual` or `google_places`
  - `enrichment_mode`: `link_only` or `google_enriched`
  - `google_photo_name` or equivalent photo resource reference
  - `google_photo_attributions`: JSON metadata needed for display attribution
  - `google_photo_media_asset_id`: optional copied/cached media asset id, if the implementation stores the selected Google image locally
  - `google_about`: optional Google-provided summary/about text
  - `google_about_source_field`: for example `editorial_summary` or another official Places field
  - `google_fetched_at`

Do not scrape Google Maps pages. Pull place details and photos only from official Google Maps Platform Places APIs.

### `MediaAsset`

No activity-specific media table is needed. Activity post photos should continue to attach through `MediaAsset.post_id`.

When an activity post is attached to a stop, keep the existing behavior of also setting `MediaAsset.stop_id` so stop galleries can include activity photos.

## Google Maps POI Behavior

When linking a Google Maps Place POI, the admin chooses one of two modes.

### Link Only

Use this when the owner only wants to attach the place identity and outbound Google Maps link.

Store:

- Google Maps URL or place id when available
- place label
- formatted address and coordinates when available

Reader display:

- place card with name/address
- "Open in Google Maps" link
- no Google-provided image or about text

### Google Enriched

Use this when the owner wants Postmarked to pull optional Google place context.

Fetch:

- selected Google place photo, if available
- Google-provided about/summary text, if available from official Places fields
- attribution/source metadata required for compliant display

Reader display:

- place card with name/address and map link
- optional Google place image
- optional Google about text
- clear source/attribution display for Google-provided content

Fallback:

- If Google has no image/about text or the API request fails, save the POI as link-only and show a non-blocking admin message.
- The owner can still use their own post body and uploaded photos.

## API Design

### Admin APIs

Extend existing post create/update endpoints to accept:

- `post_type`
- `activity_type`
- `summary`
- `activity_started_at`
- `activity_ended_at`
- `poi_id`

Add or extend POI endpoints for:

- create/update/delete a POI under a stop
- search/resolve a Google Place
- save a POI in link-only mode
- enrich a POI with Google photo/about fields
- detach a POI from a post without deleting the reusable POI

Post updates should continue to support quick updates with only title/body/stop/media fields.

### Public APIs

Extend public post serialization with allowlisted activity fields:

- `post_type`
- `activity_type`
- `summary`
- `activity_started_at`
- `activity_ended_at`
- public POI display fields

Stop detail should return stop-attached posts in a way the frontend can group:

- quick updates
- activity posts

Add a public post detail endpoint for richer activity pages:

```text
GET /api/trips/{trip_slug}/stops/{stop_slug}/posts/{post_slug}
```

The response should include:

- post title, summary, body, type, activity metadata
- trip and stop handles
- visible post media
- optional POI card data
- previous/next post or activity siblings within the stop, if useful

## Reader Experience

### Stop Detail

Stop detail should make the new layer visible without hiding existing updates.

Recommended structure:

- stop hero and stop gallery
- stop description/body
- "Activities from this stop" section for `post_type="activity"`
- "Updates from here" section for `post_type="update"`
- comments on the stop

Activity cards should show:

- title
- summary or body excerpt
- activity type chip
- activity date/time when available
- thumbnail from post media, cover media, or Google place image
- place label when linked

### Activity Post Detail

Activity post detail should feel like a local story page.

Include:

- breadcrumb: trip -> stop -> activity
- title, activity type, date/time
- summary and body
- photo gallery
- optional place card
- optional Google image/about section when enabled
- comments using existing `CommentsIsland` with `targetKind="post"`
- previous/next activity navigation within the same stop

### Timeline And Home

Quick updates should remain the main recent feed behavior.

Activity posts may appear in the timeline, but the UI should label them as activities so a restaurant night or hike reads differently from a quick current-location note.

## Admin Experience

### Composer

Broaden the current Quick Post composer into a post composer with a mode selector:

- Quick update
- Activity

Quick update mode remains minimal:

- title
- body
- stop
- visibility
- photos

Activity mode adds:

- activity type
- optional summary
- optional activity date/time
- optional Google Maps Place POI

### POI Panel

The activity editor should support:

- paste a Google Maps URL or search/select a place
- choose `Use link only`
- choose `Pull Google image/about`
- preview the place card before saving
- remove the linked POI from the post
- replace Google image/about with owner-written text and uploaded photos

Google enrichment should never be required to publish an activity.

### Existing Posts Admin

The posts list should add filters or chips for:

- quick updates
- activities
- stop
- visibility

Editing an old post should default to quick update mode unless the owner changes it to activity.

## Privacy And Visibility

Activity posts use the same effective visibility rule as posts today:

- A public activity under a private stop is private.
- A private activity under a public stop is private.
- Approved users and admins follow the existing access rules.
- Anonymous/public responses only return allowlisted fields.

Google enrichment content should follow the POI/post visibility. A Google image or about text attached to a private activity should not appear in public responses.

## Migration And Rollout

1. Add database migration for new `Post` fields and expanded `PointOfInterest` fields.
2. Backfill existing posts to `post_type="update"`.
3. Update schemas and serializers.
4. Update admin post create/edit flows.
5. Add POI link/enrichment backend support.
6. Update public stop detail to group activities and updates.
7. Add post/activity detail page.
8. Seed sample activity posts for one demo stop.
9. Update docs and API contracts after implementation.

No existing public URLs need to break. Current stop detail pages can keep rendering posts while the activity grouping is introduced.

## Testing

Backend tests:

- create quick update post with old minimal payload
- create activity post with optional fields
- update existing post from update to activity
- attach and detach POI
- save link-only POI
- save Google-enriched POI
- fallback to link-only when Google enrichment fails
- public serialization omits private and internal Google metadata
- comments still work on `target_kind="post"`
- media attached to activity posts appears in post and stop contexts

Frontend checks:

- quick post composer still works on mobile
- activity mode reveals additional fields
- stop detail separates activities from updates
- activity cards render with and without media
- place card renders in link-only mode
- place card renders with Google image/about when available
- activity comments load and post correctly
- existing trip, timeline, stop, post, media, and comment flows still work

## Open Implementation Notes

- Confirm which official Google Places summary/about fields are available for the configured API and billing tier.
- Decide whether Google place photos are displayed by proxying/caching into `MediaAsset` or by using a short-lived official photo URL flow.
- Add attribution display before shipping Google-enriched POI content publicly.
- Keep the first implementation focused on manual owner control, not automatic enrichment for every place.
