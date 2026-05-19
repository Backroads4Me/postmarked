# Postmarked Docs

Current project documentation. Read in this order:

1. `../README.md` — How to run, test, import, and deploy.
2. `api-contracts.md` — Public reader API contracts used by the frontend.
3. `post-activities-design.md` — Proposed design for stop activity posts with optional Google Maps POI enrichment.
4. `rv-trip-wizard-excel-import.md` — RV Trip Wizard Excel import and reimport behavior.
5. `path-to-testing.md` — Testing checklist and polish backlog.

## Current Product Decisions

- Postmarked is a lightweight travel journal — quick updates, not blogging or trip planning.
- The FastAPI/Astro/PostGIS/Docker foundation is stable.
- Trips are segments or chapters inside a continuous journey.
- RV Trip Wizard Excel is the only supported external import format.
- Manual stop creation and editing are first-class.
- Public reader APIs are privacy-safe by explicit allowlist.
- Google Maps is the map provider.
