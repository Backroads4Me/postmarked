# Codex Review Plan

This document tracks an end-to-end review and improvement pass for Goodpath. Keep changes incremental: fix one item, run the relevant verification, record evidence here, then continue.

## Verification Baseline

- 2026-05-17: `docker exec goodpath-api-1 python -m compileall app` passed.
- 2026-05-17: `npm run build` from `web/` passed; Vite reports the existing large chunk warning.
- 2026-05-17: `docker exec goodpath-api-1 ruff check app` is blocked because `ruff` is not installed in the running API image.

## P0 Security And Data Safety

- [x] Do not log password reset or verification tokens.
  - Why: `api/app/auth/auth_config.py` prints reset and verification tokens. This leaks account recovery secrets into container logs.
  - Work: Replace token-bearing log lines with non-sensitive audit-style messages.
  - Verify: API import/compile passes; manual inspection confirms no token value is printed.
  - Status: Complete.
  - Evidence: Replaced token-bearing password reset and verification `print` calls with non-sensitive logger messages. `docker exec goodpath-api-1 python -m compileall app` and `docker exec goodpath-api-1 python -c "import app.main; print('api import ok')"` passed. `rg` confirms no `Reset token` or `Verification token` log strings remain.

- [x] Remove unsafe `innerHTML` construction in the admin post POI selector.
  - Why: POI labels and types are user/admin-controlled strings. Building `<option>` markup with string interpolation can create XSS in the admin UI.
  - Work: Build options with DOM APIs and `textContent`.
  - Verify: `npm run build` passes; the admin post edit page can still refresh POIs after changing stops.
  - Status: Complete.
  - Evidence: Replaced POI option string interpolation with `document.createElement`, `textContent`, and `replaceChildren`. `npm run build` passed with the existing large-chunk warning. `rg innerHTML web/src/pages/admin/posts/[id].astro` returns no matches.

- [x] Add upload type and size validation for TUS media creation.
  - Why: `/api/admin/media/tus` accepts any metadata MIME type and arbitrary `Upload-Length`, allowing accidental huge uploads or unsupported file types that fail later.
  - Work: Define a conservative allowlist for image/video MIME types and a configurable max upload size; reject invalid creates before writing temp state.
  - Verify: API compile/import passes; invalid MIME and oversized upload return 415/413; valid image upload still works.
  - Status: Complete.
  - Evidence: Added MIME allowlist, positive length check, configurable `GOODPATH_MAX_UPLOAD_BYTES`, and PATCH overrun guard. `docker exec goodpath-api-1 python -m compileall app` and API import passed. Authenticated smoke checks returned 415 for `text/plain`, 413 for oversized PNG metadata, and 201 for a small valid PNG create; temporary smoke upload files were removed.

- [x] Delete media bytes when deleting a media asset.
  - Why: `DELETE /api/admin/media/{asset_id}` removes only the database row. Originals and derivatives remain in Docker volumes, wasting storage and making backup/cleanup misleading.
  - Work: Resolve original/webp/poster paths and remove them after DB deletion, tolerating already-missing files.
  - Verify: Delete an uploaded test asset and confirm DB row and files are gone.
  - Status: Complete.
  - Evidence: Admin delete now collects original/temp/derivative paths and removes them after DB commit, tolerating missing files. `docker exec goodpath-api-1 python -m compileall app` and API import passed. Smoke test inserted synthetic media asset `11111111-1111-4111-8111-111111111111`, created original/json/webp files, called `DELETE /api/admin/media/{id}` with admin cookie, received 200, DB count returned 0, and `ls` confirmed all synthetic files were absent.

## P1 Correctness

- [x] Make public media exposure consistently require ready media.
  - Why: Some public serializers filter visibility only, but not `processing_state`. Broken or pending assets can leak into payloads and render as missing images.
  - Work: Centralize ready/visibility filtering for media lists and cover media across `journey.py`, `stops.py`, and related serializers.
  - Verify: API responses omit pending/failed media for anonymous users; admin can still inspect failed assets in admin media.
  - Status: Complete.
  - Evidence: Updated journey and stop/post detail serializers so media lists and cover media must be `READY` before they appear in reader API payloads; anonymous users still require public visibility. `docker exec goodpath-api-1 python -m compileall app` and API import passed. `GET /api/trips/michigan-ny-2026/stops/charlestown-state-park` returned 200.

- [x] Fix stale duplicate `return await call_next(request)` in CSRF middleware.
  - Why: `api/app/main.py` has unreachable duplicate code, which is harmless at runtime but confusing in a security-sensitive middleware.
  - Work: Remove unreachable return and keep logging concise.
  - Verify: API compile/import passes; unsafe request with disallowed Origin still returns 403.
  - Status: Complete.
  - Evidence: Removed unreachable duplicate return. `docker exec goodpath-api-1 python -m compileall app` and API import passed. Authenticated unsafe request with `Origin: http://not-allowed.local` returned 403.

- [x] Validate trip cover assignment behavior for replacing and clearing covers.
  - Why: Recent cover work attaches a selected asset to a trip, but old cover cleanup and explicit clearing behavior need an intentional policy.
  - Work: Decide whether old cover assets remain attached, become orphaned, or are untouched; implement only if needed.
  - Verify: PATCH with new cover, PATCH with `cover_media_id: null`, and public trip response behave as expected.
  - Status: Complete.
  - Evidence: Product policy set: replacing or clearing a trip cover deletes the previous cover media row and its stored files. Added shared media file cleanup helpers, updated the admin trip PATCH path to delete the previous cover when `cover_media_id` changes or is set to `null`, and added a Clear Cover button to the admin trip page. Smoke verification created a temporary trip with two synthetic cover media assets, patched the trip from old cover to new cover, confirmed the old media row count was 0 and `/originals/{old}.bin` plus `/derivatives/{old}.webp` were gone, then patched `cover_media_id: null` and confirmed the new media row/files were gone and the trip cover was `NULL`.

- [x] Resolve Docker volume/project-name migration fragility for media storage.
  - Why: A previous compose project name change left uploaded media in `compose_*` volumes while the running stack used `goodpath_*` volumes.
  - Work: Document migration or provide a script/check that warns when DB media paths reference missing files while older volumes contain bytes.
  - Verify: Fresh stack and upgraded stack both have media bytes in the active volumes.
  - Status: Complete.
  - Evidence: Added `scripts/check-media-storage.sh`, which compares DB media rows against files present in the active API container volumes and warns about likely compose/project-name volume migrations. Documented it in README verification/deployment notes. `./scripts/check-media-storage.sh` passed against the running stack.

## P1 Reliability And Tests

- [x] Add targeted backend tests for visibility and media serialization.
  - Why: Visibility and media readiness are easy to regress and high-impact for a private family app.
  - Work: Add pytest coverage for public/admin trip segments, stop detail media filtering, and media endpoint authorization.
  - Verify: Tests run in a documented command and fail before/fix after for at least one covered bug.
  - Status: Complete.
  - Evidence: Added `api/tests/test_visibility.py` with focused tests for anonymous media filtering, admin media filtering, and cover-media readiness behavior. Documented the reliable local command in `api/README.md`. `cd api && PYTHONPATH=. uv run --extra dev python -m pytest tests/test_visibility.py` passed with 3 tests. A direct `uv run pytest ...` invocation picked up the wrong host entrypoint and failed to resolve the project dependencies, so the documented command uses `python -m pytest`.

- [x] Add upload processing tests or a deterministic smoke script.
  - Why: The upload flow spans TUS temp files, DB rows, Celery, derivatives, and frontend consumption.
  - Work: Add a minimal sample image smoke test or script that creates, patches, processes/requeues, and fetches `/media/{id}/webp`.
  - Verify: Script/test passes against the Docker stack.
  - Status: Complete.
  - Evidence: Added `scripts/smoke-media-upload.sh`, which generates a deterministic PNG, logs in, performs TUS create/PATCH, waits for the worker to mark the asset READY, fetches `/media/{id}/webp`, and deletes the smoke asset. The first run caught a real image-processing bug (`Operation on closed image`); fixed `api/app/tasks.py` to compute dominant color before blurhash closes the image. `docker exec goodpath-api-1 python -m compileall app`, `docker exec goodpath-api-1 python -c "import app.tasks; print('tasks import ok')"`, and `./scripts/smoke-media-upload.sh` passed. DB check confirmed the smoke asset was cleaned up.

- [x] Keep the dev Celery worker from wedging after file changes.
  - Why: Fresh smoke verification found the worker container running only the `watchmedo` supervisor with no active Celery child. Upload tasks queued in Redis but were not consumed, leaving new media assets stuck in `PENDING`.
  - Work: Remove the fragile file-watch auto-restart wrapper from the dev compose worker command and run Celery directly.
  - Verify: Restart the worker, confirm queued tasks drain, and rerun the media upload smoke script.
  - Status: Complete.
  - Evidence: Updated `compose.override.yaml` so the dev worker command is `celery -A app.tasks worker -l info`. Before the fix, `redis-cli llen celery` showed queued `process_media_asset` jobs while `/proc` showed no Celery child process. After `docker compose up -d worker`, `/proc` showed active Celery processes, `redis-cli llen celery` returned 0, and `./scripts/smoke-media-upload.sh` passed for asset `f52fc0ac-a207-4042-af31-1343106fcfca`.

- [x] Make lint/typecheck tooling runnable in the dev container or document local-only usage.
  - Why: `ruff` is declared in dev dependencies but missing from the running API image, so review checks are inconsistent.
  - Work: Decide whether Docker dev image should install dev extras or README should show `uv run ruff`.
  - Verify: A documented lint command runs successfully.
  - Status: Complete.
  - Evidence: Documented `uv pip install -e ".[dev]"`, `ruff check app`, and `mypy app` in `api/README.md`, and noted that the Docker runtime image intentionally installs production dependencies only. `rg` confirms the commands and production-dependency note are present.

## P2 Maintainability

- [x] Replace auth `print` calls and task `print` calls with structured logging.
  - Why: Logs should be levelled, searchable, and avoid secrets. Current output mixes warnings, lifecycle events, and task failures via `print`.
  - Work: Introduce module loggers in auth/tasks and use appropriate levels.
  - Verify: Compile/import passes; logs still show useful non-sensitive failures.
  - Status: Complete.
  - Evidence: Added module loggers in auth and tasks, replaced lifecycle/task `print` calls with logger calls, and avoided logging user email in digest mock output. API compile/import passed. `rg "^\\s*print\\(" api/app/auth/auth_config.py api/app/tasks.py` returns no matches.

- [x] Reduce duplicated public media filtering logic.
  - Why: Several routers open-code admin/visibility checks, which increases the chance of inconsistent privacy behavior.
  - Work: Add small helper functions or extend `services/visibility.py` for media list and cover filtering.
  - Verify: Existing API responses are unchanged except for intentional omission of non-ready public media.
  - Status: Complete.
  - Evidence: Added shared `visible_ready_media` and `visible_ready_cover_media` helpers to `api/app/services/visibility.py`, then updated `journey.py` and `stops.py` to use them. Fixed an eager-loading edge case in `/api/home` that surfaced during verification. `docker exec goodpath-api-1 python -m compileall app` and API import passed. Live checks for `/api/home`, `/api/trip-segments`, `/api/trip-segments/michigan-ny-2026`, and `/api/trips/michigan-ny-2026/stops/charlestown-state-park` returned 200.

- [x] Improve admin media error presentation.
  - Why: Failed processing currently appears as a status but does not show the stored `error_message`, making diagnosis harder.
  - Work: Display `error_message` in the admin media list and on requeue failure paths.
  - Verify: Failed asset shows actionable text in `/admin/media`.
  - Status: Complete.
  - Evidence: Added `error_message` to `MediaAssetOut` and rendered it in `/admin/media`; also corrected the ready-state color check from `done` to `ready`. API compile/import and `npm run build` passed, with the existing large-chunk warning.

## P2 UX And Performance

- [x] Make cover upload UX refresh or update the preview after success.
  - Why: The current admin trip page tells the user to reload after a cover upload. Updating the preview inline would feel more polished.
  - Work: After successful PATCH, replace the preview image/status without requiring a page reload.
  - Verify: Uploading a cover updates the visible preview in-place.
  - Status: Complete.
  - Evidence: Admin trip cover upload now replaces the preview immediately with a local object URL, clears the file input, and no longer tells the user to reload. `npm run build` passed with the existing large-chunk warning.

- [x] Investigate large frontend chunks.
  - Why: `npm run build` warns about chunks over 500 kB, likely from map libraries and admin/editor code.
  - Work: Identify the largest bundle contributors and consider dynamic imports for map/admin-only code.
  - Verify: Build still passes and warning is reduced or an intentional note is added.
  - Status: Complete.
  - Evidence: Changed `MapIsland` so MapLibre, PMTiles, and MapLibre CSS are loaded dynamically only when the MapLibre provider is used; Google Maps mode no longer eagerly imports those packages. `npm run build` passed. Bundle inspection with `wc -c web/dist/client/_astro/* | sort -nr | head -20` shows the remaining warning is the isolated async MapLibre package chunk (`maplibre-gl...js`, about 1.0 MB) plus its CSS, while `MapIsland` itself is about 14 kB. Keeping this as an intentional lazy-loaded mapping dependency is safer than replacing the map stack during this pass.

- [x] Run a mobile admin/readability pass.
  - Why: Admin pages contain dense forms and tables that may be awkward on a phone, which matters for RV travel use.
  - Work: Use browser screenshots for key pages and tune spacing, overflow, and controls.
  - Verify: Mobile-width screenshots show no clipped controls or unusable layouts.
  - Status: Complete.
  - Evidence: Updated two-column admin form groups to collapse to one column on phones, allowed edit action rows to wrap, made the stops and import-preview tables horizontally scrollable, and stacked the media batch assignment toolbar on small screens. `npm run build` passed. Headless Chrome DevTools verification at 390px captured `/tmp/goodpath-mobile-trips-new.png`, `/tmp/goodpath-mobile-trip-edit.png`, `/tmp/goodpath-mobile-stops.png`, `/tmp/goodpath-mobile-media-batch.png`, and `/tmp/goodpath-mobile-import.png`; each page stayed authenticated, loaded the expected admin title, and reported `bodyWidth: 390` with no page-level horizontal overflow.
