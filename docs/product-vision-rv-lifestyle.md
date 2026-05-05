# Goodpath Product Vision: Full-Time RV Life Sharing

Status: current product direction  
Last updated: 2026-05-04

## Decision

Goodpath should be a purpose-built full-time RV lifestyle sharing app, not a generic travel tracker. Trips matter, but they are secondary to the continuous story of living and moving in the RV.

The product should answer four family-facing questions immediately:

- Where are they now?
- What have they shared in the last few days?
- Where have they been recently?
- Where are they headed next?

## Reference Research

Polarsteps is useful for interaction inspiration: it has trip planning, automatic route tracking, step-by-step updates, photos/videos/stories, privacy controls, offline-friendly tracking, and family/friend following. Its own support docs describe "Steps" as locations inside a trip that contain text, photos, videos, activities, comments, and map pins.

Finding Penguins is useful for the "travel journal + route + photos + stories + travel book" framing. Its app description emphasizes tracking, planning, sharing, posts about places visited, and route visualization.

AdventureLog is useful as an open-source technical/product reference for self-hosted travel tracking: locations, maps, public/private sharing, itineraries, categories, activities, GPX attachments, and Docker deployment. It is not the correct product base because its center is generic locations/itineraries, while Goodpath's center must be an active RV household and continuous timeline.

Sources:

- Polarsteps product site: https://www.polarsteps.com/
- Polarsteps tracker support: https://support.polarsteps.com/article/80-how-does-the-travel-tracker-work-does-it-use-gps
- Polarsteps step support: https://support.polarsteps.com/article/71-what-are-steps-and-how-do-i-add-or-edit-them
- Finding Penguins App Store listing: https://apps.apple.com/us/app/findpenguins-travel-tracker/id721334305
- AdventureLog GitHub: https://github.com/seanmorley15/AdventureLog
- AdventureLog site: https://adventurelog.app/

## Product North Star

Goodpath is the private family window into a full-time RV life.

It combines:

- A live-ish current location.
- A continuous timeline of stops and posts.
- Trip segments for plans, seasons, loops, and stories.
- RV-specific stop and travel metadata.
- Manual logging for any user.
- RV Trip Wizard Excel import and reimport for users who plan externally.
- Rich, low-friction family sharing.

## Target Users

### Owner / Publisher

The person or couple living in the RV. They need fast publishing while traveling, import/reimport from RV Trip Wizard, manual stop editing, photo upload, privacy controls, and a low-maintenance way to keep family updated.

### Family / Friends

Readers who want a simple, pleasant view of where the RV is and what has happened recently. They should not need to understand trip planning tools or app mechanics.

### Anonymous Visitor

Optional public reader who can see only public content, if the owner chooses to publish publicly.

## Product Pillars

### 1. Current Presence

The home screen should lead with current presence:

- Current stop or current pin.
- Arrival date and "here for X nights" if known.
- Last update timestamp.
- Short current note.
- Next planned destination.

This should feel like "checking in" on family, not browsing a database.

### 2. Continuous Timeline

The primary browsing model is a continuous RV life timeline. Trips are filters/chapters on top of that timeline.

Timeline items include:

- Planned stops.
- Active/current stop.
- Past stops.
- Posts.
- Photos/videos.
- Travel days.
- Plan changes.

### 3. RV-Specific Stops

Stops should understand RV life:

- Campground / boondocking / Harvest Host / service / attraction / family / overnight / fuel / restaurant / other.
- Arrival and departure.
- Nights.
- Site number / reservation info.
- Hookups.
- Pull-through/back-in.
- Big rig access.
- Dump station.
- Cost.
- Mileage and travel time from previous stop.
- Fuel used/added.
- Would stay again.
- Pet/kid notes if desired.

### 4. Plan-To-Life Workflow

Imported plans are not the same as lived stops. A planned stop can become a lived stop, and reimporting a changed plan must not destroy journal content.

### 5. Family Sharing

Sharing should optimize for family:

- Latest updates feed.
- Simple comments/reactions.
- Email digest later.
- Private links or approved accounts.
- No generic social network complexity.

## MVP Product Shape

### Public / Reader Screens

1. **Home**
   - Current location hero.
   - Recent updates from last 3-7 days.
   - Map preview with current stop, recent stops, and next stop.
   - Next up card.
   - Link to live timeline.

2. **Live Timeline**
   - Continuous chronological feed.
   - Newest-first default for family.
   - Toggle to route-order/progress mode.
   - Stop groups with posts/photos.

3. **Trip Progress View**
   - Interactive map and timeline scrubber.
   - As user scrolls or drags the timeline, map focuses on the matching stop/leg and photos scroll in a synchronized carousel.
   - Stop drill-in opens a detailed stop page. The full synchronized scrubber/carousel interaction remains post-MVP polish.

4. **Stop Detail**
   - Story, photos, map, RV details, reservation-safe public fields, and comments for approved readers.

5. **Trip Segment Page**
   - Optional chapter view for a named trip/plan.
   - Good for sharing "Michigan, NY 2026" while still preserving the continuous full-time timeline.

### Admin Screens

1. **Dashboard**
   - Current stop.
   - Quick post.
   - Add stop.
   - Import RV Trip Wizard Excel.
   - Recent draft/private items.

2. **Plan Import**
   - Upload Excel.
   - Preview parsed stops.
   - Diff against prior import.
   - Confirm added/changed/canceled stops.

3. **Stops**
   - Manual add/edit.
   - Convert planned stop to lived stop.
   - Attach posts/photos.

4. **Posts / Media**
   - Fast photo/story updates.
   - Attach to current stop by default.

## What To Defer

Defer until after the core experience feels good:

- GPX/ICS/CSV import.
- Automatic phone GPS tracking.
- Full PMTiles self-hosted basemap pipeline.
- Heavy media processing with TUS/Celery.
- Notifications/digests.
- Multi-author collaboration.
- Travel book generation.
- Public profile/social discovery.

## Build vs Fork Decision

Do not fork AdventureLog as the base application.

Use AdventureLog as:

- A feature checklist reference.
- A deployment and self-hosting reference.
- A UI comparison point for maps, locations, and planning.

Keep Goodpath custom because:

- The primary object is continuous RV life, not discrete trips.
- RV Trip Wizard Excel import/reimport is central.
- RV-specific stop metadata should be first-class.
- Family-current-location sharing is the home experience, not a secondary feature.
