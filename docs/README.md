# Goodpath Docs

These are the current, useful project docs. Old agent handoff trackers and superseded implementation plans have been removed so this directory stays readable.

Read in this order:

1. `../README.md`
   - How to run, test, import, and deploy the current MVP.
2. `product-vision-rv-lifestyle.md`
   - Product intent: continuous full-time RV life sharing, not a generic travel app.
3. `rv-mvp-api-contracts.md`
   - Current public reader API contracts used by the frontend.
4. `post-activities-design.md`
   - Proposed design for building local stop activities on top of posts, including optional Google Maps POI enrichment.
5. `rv-trip-wizard-excel-import.md`
   - RV Trip Wizard Excel import and reimport behavior.
6. `path-to-testing.md`
   - Current local testing checklist and non-blocking polish backlog.
7. `../goodpath-design.md`
   - Longer-term product/design specification. Treat this as directional when it goes beyond the current MVP.

## Current Product Decisions

- Preserve the FastAPI/Astro/PostGIS/Docker foundation.
- Model the product around one continuous full-time RV journey.
- Treat trips as segments or chapters inside that journey.
- Support RV Trip Wizard Excel as the only MVP external import format.
- Keep manual stop creation and editing first-class.
- Keep public reader APIs privacy-safe by explicit allowlists.
