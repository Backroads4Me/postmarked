# Goodpath Implementation Plan for AI Coding Agents

## Purpose
This document converts [`goodpath-design.md`](/home/ted/github/goodpath/goodpath-design.md) into an execution plan for AI coding agents. It is optimized for parallel work, small reviewable changes, and clear ownership boundaries. The product spec remains the source of truth for behavior; this plan defines sequencing and delivery.

## Delivery Principles
- Build the repository skeleton first so later agents work against stable paths and conventions.
- Land vertical slices, not disconnected subsystems. Each phase should end in something runnable.
- Keep write ownership narrow. One agent should own one service area or one isolated file set at a time.
- Prefer generated fixtures and seed data early so frontend and backend can progress in parallel.
- Enforce security and visibility rules from the first API endpoint. Do not defer them to cleanup.

## Target Repository Layout
Create the structure defined in spec section 2.5:

```text
compose/
caddy/
api/
web/
scripts/
docs/
pmtiles/
```

Add `README.md`, `docs/architecture.md`, `docs/operations.md`, `.env.example`, and CI config in the first phase.

## Phase 0: Foundation and Tooling
Goal: produce a bootable monorepo with Docker Compose, local dev, linting, tests, and CI.

Deliverables:
- `compose/docker-compose.yml` and `docker-compose.dev.yml`
- Caddy, Postgres/PostGIS, Redis, API, web, worker, beat, Flower services
- FastAPI app boot scaffold with health endpoints
- Astro app boot scaffold with the design prototype adapted into layouts/components
- Alembic, pytest, Ruff, mypy, ESLint, TypeScript, Prettier, Playwright setup
- pre-commit or equivalent formatting hooks

Acceptance criteria:
- `docker compose up` boots the full stack
- `/api/health` and `/api/health/ready` respond correctly
- CI runs lint + unit tests for `api` and `web`

Agent split:
- Agent A: Compose/Caddy/dev environment
- Agent B: API scaffold and Python tooling
- Agent C: Web scaffold and frontend tooling

## Phase 1: Data Model and Auth Baseline
Goal: establish the core schema and secure account flows before content features.

Deliverables:
- SQLAlchemy models and Alembic migrations for users, trips, stops, media, comments, likes, collections, notification preferences, audit log, RV profile, about profile, scan sources, notification log
- enums and visibility inheritance helpers
- `fastapi-users` integration with Argon2id, secure cookies, email verification, password reset
- Google OAuth wiring behind env flags
- role and approval guards

Acceptance criteria:
- pending users authenticate but only see public content
- unauthorized access to private resources returns `404`
- migration from empty DB succeeds and seeds one admin account

Agent split:
- Agent A: models and migrations
- Agent B: auth flows and approval workflow
- Agent C: frontend auth pages and session-aware nav

## Phase 2: Public Read Model and Seeded Reader Experience
Goal: make the public reader usable with seeded demo data before admin tooling exists.

Deliverables:
- read-only endpoints for home, trips index, trip detail, stop detail, map, timeline, places, collections, RV, about
- shared Pydantic response models optimized for overview vs detail payloads
- frontend routes in Astro with React islands only for map/lightbox/timeline interactions
- seed script with at least 2 trips, multiple stops, mixed visibility, media metadata, comments, and likes

Acceptance criteria:
- all public pages render from live API data
- visibility filtering is applied in SQL for list and detail queries
- mobile nav and desktop nav match spec section 9

Agent split:
- Agent A: read endpoints and query layer
- Agent B: Astro pages and shared UI primitives
- Agent C: seed fixtures and API/client contract tests

## Phase 3: Admin CRUD for Core Content
Goal: let the owner manage trips, stops, RV/about profiles, collections, users, settings.

Deliverables:
- `/admin/*` layout and route guards
- trip CRUD, stop CRUD, drag reorder, map-click create
- RV/about/settings/users/comments moderation pages
- audit log entries for approval, role changes, publish/delete, settings updates

Acceptance criteria:
- admin can create a planned trip, add stops, reorder them, and publish
- audit records are created for all required actions
- non-admin users cannot access admin routes or endpoints

Agent split:
- Agent A: admin API routes and services
- Agent B: admin web UI shell and shared form patterns
- Agent C: trip-builder map interactions

## Phase 4: Media Upload and Processing Pipeline
Goal: support reliable ingestion before advanced browsing is finalized.

Deliverables:
- TUS upload endpoint for photos and videos
- media asset records, processing states, retry support
- Celery pipeline for metadata extraction, EXIF, SHA-256 dedup, orientation, thumbnails, AVIF/WebP/JPEG derivatives, blurhash, dominant color, video poster extraction
- `/admin/intake`, `/admin/media/{id}`, `/admin/jobs`

Acceptance criteria:
- resumable upload works for large files
- duplicate uploads are surfaced without reprocessing originals
- failed jobs can be retried from admin
- media streaming endpoint supports `Range`, `ETag`, and private access rules

Agent split:
- Agent A: TUS + media models + storage abstraction
- Agent B: Celery tasks and ffmpeg/Pillow pipeline
- Agent C: intake/jobs/admin UI

## Phase 5: Filesystem Scan Import and Batch Assignment
Goal: implement the second ingestion path and reduce manual organization work.

Deliverables:
- scan source configuration
- scheduled/manual scanner jobs
- EXIF GPS clustering hints for stop creation
- batch assignment UI from intake to stops

Acceptance criteria:
- scanner walks configured paths idempotently
- exact dedup is SHA-based
- near-duplicate hints appear in admin only

## Phase 6: Synchronized Map, Timeline, and Lightbox
Goal: build the product’s differentiator after the core data paths are stable.

Deliverables:
- MapLibre React island with PMTiles support
- URL-driven synchronized state for `trip`, `stop`, `media`, and `view`
- timeline rail/strip, media grid, lightbox interactions, route rendering, POI markers
- virtualization where views exceed 200 items

Acceptance criteria:
- shareable URL restores the same map/timeline/media state
- back/forward navigation works without state drift
- desktop and mobile interaction patterns match spec sections 8 and 9

Agent split:
- Agent A: map state/store and URL contract
- Agent B: lightbox and media browsing
- Agent C: timeline and virtualization

## Phase 7: Social, Search, and Notifications
Goal: finish reader-facing engagement and discovery.

Deliverables:
- flat comments, likes, moderation, sanitized markdown
- Postgres full-text search across required entities
- notification preferences, publish-trigger fan-out, digest jobs, unsubscribe flow, test-send endpoint

Acceptance criteria:
- approved + verified users can comment and like
- anonymous and pending users cannot perform those actions
- digests are idempotent and logged

## Phase 8: PWA, Performance, Accessibility, and Operations
Goal: harden the system for V1 release.

Deliverables:
- service worker and offline-tolerant app shell
- Lighthouse and LCP tuning
- accessibility pass for keyboard, focus, labels, reduced motion, color contrast
- backup/restore scripts, operations docs, deployment docs, rate limits, CSP/HSTS/security headers

Acceptance criteria:
- performance budgets in spec section 13 are met or documented with a gap list
- `scripts/backup.sh` and `scripts/restore.sh` work on a fresh environment
- release checklist is documented

## Cross-Cutting Rules for Agents
- Do not combine schema work, frontend feature work, and infra refactors in one change unless required.
- Every backend feature must include tests for visibility and authorization when applicable.
- Every frontend feature must include mobile-width verification and loading/empty/error states.
- Add fixtures or seeds for new entities so parallel agents can build against realistic data.
- Keep API contracts explicit in typed schemas; do not let the web app depend on ORM internals.
- If a task touches private media, auth, comments, or search, include a regression test for non-leakage.

## Recommended Branch and PR Strategy
- Use short-lived branches per phase or per bounded subsystem.
- Keep PRs under roughly 500 changed lines when possible.
- Merge in this order: schema -> services -> API -> frontend -> ops/docs.
- Require passing CI before merging any branch that changes schema, auth, or storage behavior.

## Definition of Done
A phase is done only when:
- code, tests, and migrations are merged
- docs and env vars are updated
- seed/demo data supports manual verification
- admin and public UI states are covered where relevant
- security and visibility behavior is verified, not assumed

## Suggested First Three Execution Tickets
1. Scaffold monorepo, Docker Compose stack, health checks, CI, and base docs.
2. Implement core models, migrations, seeded admin user, and auth/approval flow.
3. Convert the existing prototype screens into Astro layouts/components backed by seeded read APIs.
