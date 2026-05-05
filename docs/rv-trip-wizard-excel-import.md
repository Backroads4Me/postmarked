# RV Trip Wizard Excel Import and Reimport Plan

Status: current import design and implementation notes  
Last updated: 2026-05-04

## Decision

Use RV Trip Wizard Excel (`.xlsx`) as the only supported external import format for MVP.

Do not support GPX, ICS, or CSV import in MVP:

- CSV has coordinates and names but lacks dates, nights, costs, fuel, features, and reservation fields.
- ICS has date/location data but is event-oriented and can expose reservation details in a less structured way.
- GPX is useful for route geometry but does not contain the complete RV stop plan.
- Excel contains the richest stop plan and can support deterministic diff/reimport behavior.

## Example File Inspected

`export-examples/trip-26-05-04-07-46.xlsx`

Sheets:

- `Trip Summary`
- `Turn By Turn Directions`

Primary import source:

- `Trip Summary`

Defer:

- `Turn By Turn Directions`

## Trip Summary Structure

Rows observed:

- Row 1: trip name, e.g. `Michigan, NY 2026`
- Row 2: start date, e.g. `Start Date: Saturday, May 02, 2026`
- Row 3: trip notes
- Row 4: headers
- Row 5+: stop rows

Observed headers:

- Stop Name
- Miles
- Total
- Estimated Travel Time
- Arrival Day
- Arrival Date
- Nights
- Departure Day
- Departure Date
- Comments
- Reservation Number
- Features
- Location
- Url
- Phone
- Email
- Latitude
- Longitude
- Camping Cost
- Meals Cost
- Misc Cost
- Fuel Cost
- Stop Total Cost
- Starting Fuel
- Fuel Used
- Arrival Fuel
- Fuel Added
- Departure Fuel

## Domain Model Additions

### ImportRun

Tracks an uploaded RV Trip Wizard Excel file and the import outcome.

Fields:

- `id`
- `source_kind`: `rv_trip_wizard_xlsx`
- `original_filename`
- `file_sha256`
- `trip_title_from_file`
- `started_at`
- `finished_at`
- `status`: `parsed`, `applied`, `failed`
- `summary_json`: counts of added/changed/unchanged/removed
- `error_message`
- `created_by_user_id`

### Trip Segment

Represents the imported plan/chapter, e.g. `Michigan, NY 2026`.

Fields:

- `id`
- `journey_id`
- `title`
- `slug`
- `source_import_run_id`
- `start_date`
- `end_date`
- `notes`
- `status`: `planned`, `active`, `completed`, `archived`
- `visibility`

The current implementation uses the existing `Trip` model for this concept. Product language should still treat trips as segments inside the continuous journey.

### PlannedStop

Represents one row from the imported RV Trip Wizard plan.

Fields:

- `id`
- `journey_id`
- `trip_segment_id`
- `source_import_run_id`
- `source_row_number`
- `source_fingerprint`
- `source_sequence`
- `name`
- `arrival_date`
- `departure_date`
- `nights`
- `latitude`
- `longitude`
- `address`
- `url`
- `phone`
- `email`
- `features_raw`
- `features`: normalized array
- `comments_private`
- `reservation_private`
- `miles_from_previous`
- `total_miles`
- `estimated_travel_time`
- `camping_cost`
- `meals_cost`
- `misc_cost`
- `fuel_cost`
- `stop_total_cost`
- `starting_fuel`
- `fuel_used`
- `arrival_fuel`
- `fuel_added`
- `departure_fuel`
- `import_state`: `planned`, `changed`, `removed_from_latest_import`, `converted_to_stop`
- `matched_stop_id`: nullable FK to lived stop
- `created_at`
- `updated_at`

### ImportStopMatch

Optional audit table for reimport decisions.

Fields:

- `id`
- `import_run_id`
- `planned_stop_id`
- `incoming_fingerprint`
- `match_kind`: `exact`, `fuzzy`, `manual`, `new`, `removed`
- `confidence`
- `diff_json`

## Fingerprint Strategy

RV Trip Wizard rows may not provide a stable external ID in Excel. Use a deterministic fingerprint and fuzzy matching.

### Exact Fingerprint

Normalize and hash:

- stop name normalized
- latitude rounded to 5 decimal places
- longitude rounded to 5 decimal places
- arrival date
- departure date

Example string:

```text
adeline jay geo karis illinois beach state park|42.43007|-87.81042|2026-05-11|2026-05-15
```

### Fuzzy Match

If exact fingerprint does not match, attempt fuzzy matching within the same trip segment by:

- Coordinates within ~150 meters.
- Same or highly similar normalized stop name.
- Arrival/departure within 3 days.

If exactly one high-confidence match is found, update that planned stop.

If multiple matches are found, require manual resolution.

## Reimport Behavior

Reimport must be preview-first. Never silently mutate lived journal content.

### Parse Phase

1. Upload Excel file.
2. Store file hash and metadata.
3. Parse `Trip Summary`.
4. Validate required columns.
5. Generate incoming planned stop records in memory.
6. Compare to latest active plan for the same segment or selected segment.
7. Produce diff preview.

### Diff Categories

- `added`: incoming row has no match.
- `unchanged`: exact fingerprint and fields unchanged.
- `changed`: matched row has field differences.
- `removed`: existing planned stop not present in incoming file.
- `needs_review`: fuzzy conflict or dangerous change.

### Apply Phase

When owner confirms:

- Add new planned stops.
- Update changed planned stops.
- Mark missing planned stops as `removed_from_latest_import`, not deleted.
- Preserve `matched_stop_id` and all lived content.
- Write import audit summary.

### Dangerous Changes

Require explicit confirmation if:

- A planned stop linked to a lived stop is removed.
- A planned stop linked to a lived stop changes location.
- Date changes move an active/current stop.
- Reservation/private fields change.

## Public Privacy Rules

By default, imported RV Trip Wizard fields are private unless explicitly exposed.

Public-safe by default:

- Stop name
- Arrival/departure date if trip is public
- City/state inferred from address if desired
- Coordinates if stop visibility is public
- Features after owner approval
- URL after owner approval

Private by default:

- Reservation number
- Site number
- Comments
- Phone
- Email
- Costs
- Fuel details
- Exact future location for private trips

## Parser Implementation Notes

Backend dependency:

- `openpyxl` is required by `api/pyproject.toml`.

Current module layout:

```text
api/app/imports/
  rv_trip_wizard.py
  matching.py
api/app/routers/admin/imports.py
api/app/schemas/imports.py
```

Parser responsibilities:

- Read workbook.
- Find `Trip Summary`.
- Locate header row by finding `Stop Name`.
- Map columns by header text, not index.
- Skip fully empty rows.
- Stop parsing after a long run of empty rows.
- Parse dates into `date`, not `datetime`.
- Preserve original raw values in `raw_json` for audit/debugging.

## API Endpoints

### Parse Preview

`POST /api/admin/imports/rv-trip-wizard/preview`

Request:

- Multipart file upload.

Response:

- `import_run_id`
- `trip_title`
- `parsed_stop_count`
- `warnings`
- `diff`

### Apply Import

`POST /api/admin/imports/{import_run_id}/apply`

Request:

- Selected target journey/trip segment.
- Confirmation flags for dangerous changes.

Response:

- Counts.
- Created/updated planned stop IDs.

### Import History

`GET /api/admin/imports`

### Import Detail

`GET /api/admin/imports/{id}`

## Admin UI

Screen: `/admin/imports/rv-trip-wizard`

Flow:

1. Upload `.xlsx`.
2. Show parsed trip title and stop count.
3. Show table grouped by diff status.
4. Highlight private fields detected.
5. Let owner choose target trip segment or create one.
6. Confirm apply.
7. After apply, show "Review Plan" page.

Diff table columns:

- Status
- Sequence
- Stop name
- Arrival
- Departure
- Nights
- Location
- Miles
- Changes
- Action required

## Acceptance Criteria

- Import example Excel file successfully.
- Create a trip segment titled `Michigan, NY 2026`.
- Create planned stops with dates, coordinates, addresses, mileage, features, reservation/private notes, costs, and fuel fields.
- Reimport same file yields all unchanged.
- Editing one date in a copy yields one changed stop in preview.
- Removing one row in a copy marks one planned stop as removed, not deleted.
- Lived stops and posts are never deleted by reimport.
- Private reservation/cost/fuel fields are not exposed in public reader API.
