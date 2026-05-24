# Postmarked Docs

Current project documentation. Read in this order:

1. `../README.md` — How to run, test, import, and deploy.
2. `api-contracts.md` — Public reader API contracts used by the frontend.
3. `rv-trip-wizard-excel-import.md` — RV Trip Wizard Excel import and reimport behavior.
4. `path-to-testing.md` — Testing checklist and polish backlog.

## Current Product Decisions

- Postmarked is a lightweight travel journal — quick updates, not blogging or trip planning.
- The FastAPI/Astro/PostGIS/Docker foundation is stable.
- Trips are the top-level organizational unit; stops are locations within a trip.
- Posts are either quick updates or structured activities attached to a stop.
- RV Trip Wizard Excel is the only supported external import format.
- Manual stop creation and editing are first-class.
- Public reader APIs are privacy-safe by explicit allowlist.
- Google Maps is the map provider.
