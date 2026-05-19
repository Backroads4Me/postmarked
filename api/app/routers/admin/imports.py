"""
Admin import endpoints for RV Trip Wizard Excel import.
"""
import os
import uuid
import hashlib
import tempfile
import re
from datetime import date, datetime, time, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select

from app.db import get_async_session
from app.auth.dependencies import current_admin_user
from app.models.content import ImportRun, PlannedStop, Stop, Trip
from app.models.enums import PlannedStopImportState, StopStatus, StopType, TripStatus, Visibility
from app.models.user import User
from app.imports.rv_trip_wizard import parse_excel
from app.imports.matching import diff_import
from app.schemas.imports import (
    ImportPreviewResponse, ImportDiffItem, ImportRunOut,
    ImportApplyRequest, ImportApplyResponse, PlannedStopOut,
)
from app.services.audit import log_audit_event
from app.services.timezone import timezone_for_coords

router = APIRouter(prefix="/imports", tags=["admin-imports"])


def _json_value(value):
    if isinstance(value, date):
        return value.isoformat()
    return value


def _parsed_stop_payload(stop) -> dict:
    data = stop.to_dict()
    return {key: _json_value(value) for key, value in data.items()}


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "stop"


async def _unique_stop_slug(session: AsyncSession, trip_id: uuid.UUID, title: str, stop_id=None) -> str:
    base = _slugify(title)
    slug = base
    suffix = 2
    while True:
        query = select(Stop.id).where(Stop.trip_id == trip_id, Stop.slug == slug)
        if stop_id is not None:
            query = query.where(Stop.id != stop_id)
        existing = (await session.execute(query)).scalar_one_or_none()
        if existing is None:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def _date_to_datetime(value) -> datetime:
    parsed = _parse_date(value)
    if not parsed:
        raise HTTPException(status_code=422, detail="Imported stop is missing an arrival date.")
    return datetime.combine(parsed, time.min, tzinfo=timezone.utc)


def _optional_date_to_datetime(value):
    parsed = _parse_date(value)
    if not parsed:
        return None
    return datetime.combine(parsed, time.min, tzinfo=timezone.utc)


def _stop_private_details(payload: dict) -> dict:
    return {
        key: payload.get(key)
        for key in (
            "url",
            "phone",
            "email",
            "features_raw",
            "features",
            "camping_cost",
            "meals_cost",
            "misc_cost",
            "fuel_cost",
            "stop_total_cost",
            "starting_fuel",
            "fuel_used",
            "arrival_fuel",
            "fuel_added",
            "departure_fuel",
            "total_miles",
            "source_fingerprint",
        )
        if payload.get(key) not in (None, "", [])
    }


async def _apply_payload_to_stop(
    session: AsyncSession,
    stop: Stop,
    payload: dict,
    trip_id: uuid.UUID,
    sequence: int,
) -> None:
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    if lat is None or lon is None:
        raise HTTPException(
            status_code=422,
            detail=f"Imported stop '{payload.get('name')}' is missing latitude/longitude.",
        )

    stop.trip_id = trip_id
    stop.slug = await _unique_stop_slug(session, trip_id, payload["name"], stop.id)
    stop.title = payload["name"]
    stop.summary = payload.get("address")
    stop.location = f"POINT({lon} {lat})"
    stop.place_name = payload.get("name")
    stop.address_label = payload.get("address")
    stop.start_date = _date_to_datetime(payload.get("arrival_date"))
    stop.end_date = _optional_date_to_datetime(payload.get("departure_date"))
    stop.nights = payload.get("nights")
    stop.sort_order = sequence
    stop.status = StopStatus.DRAFT
    stop.stop_type = StopType.CAMPGROUND
    stop.visibility = Visibility.PRIVATE
    stop.timezone_id = timezone_for_coords(lat, lon)
    stop.rv_features = payload.get("features") or []
    stop.miles_from_previous = payload.get("miles_from_previous")
    stop.estimated_travel_time = payload.get("estimated_travel_time")
    stop.private_note = payload.get("comments")
    stop.reservation_private = payload.get("reservation")
    stop.rv_details = _stop_private_details(payload)


def _apply_payload_to_planned_stop(
    planned_stop: PlannedStop,
    payload: dict,
    trip_id: uuid.UUID,
    import_run_id: uuid.UUID,
) -> None:
    planned_stop.trip_id = trip_id
    planned_stop.source_import_run_id = import_run_id
    planned_stop.source_row_number = payload.get("row_number")
    planned_stop.source_fingerprint = payload["fingerprint"]
    planned_stop.source_sequence = payload["sequence"]
    planned_stop.name = payload["name"]
    planned_stop.arrival_date = _parse_date(payload.get("arrival_date"))
    planned_stop.departure_date = _parse_date(payload.get("departure_date"))
    planned_stop.nights = payload.get("nights")
    planned_stop.latitude = payload.get("latitude")
    planned_stop.longitude = payload.get("longitude")
    planned_stop.address = payload.get("address")
    planned_stop.url = payload.get("url")
    planned_stop.phone = payload.get("phone")
    planned_stop.email = payload.get("email")
    planned_stop.features_raw = payload.get("features_raw")
    planned_stop.features = payload.get("features") or []
    planned_stop.comments_private = payload.get("comments")
    planned_stop.reservation_private = payload.get("reservation")
    planned_stop.miles_from_previous = payload.get("miles_from_previous")
    planned_stop.total_miles = payload.get("total_miles")
    planned_stop.estimated_travel_time = payload.get("estimated_travel_time")
    planned_stop.camping_cost = payload.get("camping_cost")
    planned_stop.meals_cost = payload.get("meals_cost")
    planned_stop.misc_cost = payload.get("misc_cost")
    planned_stop.fuel_cost = payload.get("fuel_cost")
    planned_stop.stop_total_cost = payload.get("stop_total_cost")
    planned_stop.starting_fuel = payload.get("starting_fuel")
    planned_stop.fuel_used = payload.get("fuel_used")
    planned_stop.arrival_fuel = payload.get("arrival_fuel")
    planned_stop.fuel_added = payload.get("fuel_added")
    planned_stop.departure_fuel = payload.get("departure_fuel")
    planned_stop.import_state = PlannedStopImportState.PLANNED


@router.post("/rv-trip-wizard/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """
    Parse an RV Trip Wizard Excel file and return a preview diff.
    Does not write any stops — just stores the ImportRun record for later apply.
    """
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    # Save to temp file
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Parse
        parsed = parse_excel(tmp_path)

        if not parsed.stops:
            raise HTTPException(status_code=400, detail="No stops found in file")

        # Create ImportRun record
        import_run = ImportRun(
            source_kind="rv_trip_wizard_xlsx",
            original_filename=file.filename,
            file_sha256=file_hash,
            trip_title_from_file=parsed.title,
            status="parsed",
            created_by_user_id=user.id,
            summary_json={
                "parsed_stop_count": len(parsed.stops),
                "start_date": parsed.start_date,
                "notes": parsed.notes,
                "parsed_stops": [_parsed_stop_payload(stop) for stop in parsed.stops],
            },
        )
        session.add(import_run)
        await session.flush()

        # Find existing normal stops for this trip title (for diff)
        existing_stops = []
        existing_query = (
            select(
                Stop,
                func.ST_Y(cast(Stop.location, Geometry(geometry_type="POINT", srid=4326))).label("lat"),
                func.ST_X(cast(Stop.location, Geometry(geometry_type="POINT", srid=4326))).label("lon"),
            )
            .join(Trip, Stop.trip_id == Trip.id)
            .where(Trip.title == parsed.title)
            .order_by(Stop.sort_order, Stop.start_date)
        )
        result = await session.execute(existing_query)
        for stop, lat, lon in result.all():
            existing_stops.append({
                "id": str(stop.id),
                "name": stop.title,
                "source_fingerprint": (stop.rv_details or {}).get("source_fingerprint"),
                "latitude": lat,
                "longitude": lon,
                "arrival_date": stop.start_date.date() if stop.start_date else None,
                "departure_date": stop.end_date.date() if stop.end_date else None,
                "nights": stop.nights,
                "matched_stop_id": stop.id,
            })

        # Compute diff
        diff_items = diff_import(parsed.stops, existing_stops)

        # Build diff response
        diff_response = []
        for d in diff_items:
            diff_response.append(ImportDiffItem(
                status=d["status"],
                sequence=d["sequence"],
                name=d["name"],
                arrival_date=d.get("arrival_date"),
                departure_date=d.get("departure_date"),
                nights=d.get("nights"),
                location=None,
                miles=d.get("miles"),
                changes=d.get("changes", []),
                existing_id=uuid.UUID(d["existing_id"]) if d.get("existing_id") else None,
                is_dangerous=d.get("is_dangerous", False),
            ))

        # Summary counts
        summary = {
            "added": len([d for d in diff_items if d["status"] == "added"]),
            "unchanged": len([d for d in diff_items if d["status"] == "unchanged"]),
            "changed": len([d for d in diff_items if d["status"] == "changed"]),
            "removed": len([d for d in diff_items if d["status"] == "removed"]),
            "needs_review": len([d for d in diff_items if d["status"] == "needs_review"]),
        }

        await session.commit()

        return ImportPreviewResponse(
            import_run_id=import_run.id,
            trip_title=parsed.title,
            start_date=parsed.start_date,
            parsed_stop_count=len(parsed.stops),
            warnings=parsed.warnings,
            diff=diff_response,
            summary=summary,
        )
    finally:
        os.unlink(tmp_path)


@router.post("/{import_run_id}/apply", response_model=ImportApplyResponse)
async def apply_import(
    import_run_id: uuid.UUID,
    req: ImportApplyRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """
    Apply a previously parsed import. Creates/updates normal Stop records
    and optionally creates a private draft Trip.
    """
    import_run = await session.get(ImportRun, import_run_id)
    if not import_run:
        raise HTTPException(status_code=404, detail="Import run not found")
    if import_run.status != "parsed":
        raise HTTPException(status_code=400, detail="Import already applied or failed")

    parsed_data = import_run.summary_json or {}
    parsed_stops = parsed_data.get("parsed_stops") or []
    if not parsed_stops:
        raise HTTPException(status_code=400, detail="Import preview did not store parsed stops")

    # Find or create trip
    trip = None
    if req.target_trip_id:
        trip = await session.get(Trip, req.target_trip_id)
    if not trip and req.create_trip:
        slug = re.sub(r'[^a-z0-9]+', '-', (import_run.trip_title_from_file or "imported-trip").lower()).strip('-')
        # Ensure unique slug
        existing = await session.execute(select(Trip).where(Trip.slug == slug))
        if existing.scalars().first():
            slug = f"{slug}-{str(import_run.id)[:8]}"
        trip = Trip(
            slug=slug,
            title=import_run.trip_title_from_file or "Imported Trip",
            status=TripStatus.DRAFT,
            visibility=Visibility.PRIVATE,
            source_kind="rv_trip_wizard_xlsx",
            source_import_run_id=import_run.id,
        )
        session.add(trip)
        await session.flush()

    if not trip:
        raise HTTPException(status_code=400, detail="No target trip specified and create_trip is False")

    existing_result = await session.execute(select(Stop).where(Stop.trip_id == trip.id))
    existing = list(existing_result.scalars().all())
    existing_by_fingerprint = {
        stop.rv_details.get("source_fingerprint"): stop
        for stop in existing
        if stop.rv_details and stop.rv_details.get("source_fingerprint")
    }
    incoming_fingerprints = {payload["fingerprint"] for payload in parsed_stops}

    counts = {
        "added": 0,
        "updated": 0,
        "removed": 0,
        "unchanged": 0,
    }
    applied_stops = []

    for sequence, payload in enumerate(parsed_stops, start=1):
        payload = {**payload, "source_fingerprint": payload["fingerprint"]}
        stop = existing_by_fingerprint.get(payload["fingerprint"])
        if stop:
            before = {
                "name": stop.title,
                "arrival_date": stop.start_date.date().isoformat() if stop.start_date else None,
                "departure_date": stop.end_date.date().isoformat() if stop.end_date else None,
                "nights": stop.nights,
            }
            await _apply_payload_to_stop(session, stop, payload, trip.id, sequence)
            after = {
                "name": stop.title,
                "arrival_date": stop.start_date.date().isoformat() if stop.start_date else None,
                "departure_date": stop.end_date.date().isoformat() if stop.end_date else None,
                "nights": stop.nights,
            }
            counts["unchanged" if before == after else "updated"] += 1
        else:
            if payload.get("latitude") is None or payload.get("longitude") is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Imported stop '{payload.get('name')}' is missing latitude/longitude.",
                )
            start_date = _date_to_datetime(payload.get("arrival_date"))
            stop = Stop(
                trip_id=trip.id,
                slug=await _unique_stop_slug(session, trip.id, payload["name"]),
                title=payload["name"],
                location=f"POINT({payload['longitude']} {payload['latitude']})",
                start_date=start_date,
            )
            await _apply_payload_to_stop(session, stop, payload, trip.id, sequence)
            session.add(stop)
            counts["added"] += 1

        applied_stops.append(stop)

    for stop in existing:
        source_fingerprint = (stop.rv_details or {}).get("source_fingerprint")
        if source_fingerprint and source_fingerprint not in incoming_fingerprints:
            stop.status = StopStatus.ARCHIVED
            counts["removed"] += 1

    await session.flush()

    import_run.status = "applied"
    import_run.summary_json = {
        **parsed_data,
        "apply_counts": counts,
        "target_trip_id": str(trip.id),
    }

    await log_audit_event(session, user.id, "IMPORT_APPLY", "ImportRun", import_run.id, {
        "trip_id": str(trip.id),
        "trip_title": trip.title,
    })

    await session.commit()

    return ImportApplyResponse(
        import_run_id=import_run.id,
        trip_id=trip.id,
        trip_slug=trip.slug,
        counts=counts,
        stop_ids=[stop.id for stop in applied_stops],
    )


@router.get("", response_model=List[ImportRunOut])
async def list_imports(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """List all import runs."""
    result = await session.execute(
        select(ImportRun).order_by(ImportRun.created_at.desc())
    )
    return result.scalars().all()


@router.get("/planned-stops/{trip_id}", response_model=List[PlannedStopOut])
async def list_planned_stops_for_trip(
    trip_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """List imported planned itinerary rows for a trip."""
    trip = await session.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    result = await session.execute(
        select(PlannedStop)
        .where(PlannedStop.trip_id == trip_id)
        .order_by(PlannedStop.source_sequence.asc())
    )
    return result.scalars().all()


@router.get("/{import_run_id}", response_model=ImportRunOut)
async def get_import(
    import_run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_admin_user),
):
    """Get a single import run."""
    import_run = await session.get(ImportRun, import_run_id)
    if not import_run:
        raise HTTPException(status_code=404, detail="Import run not found")
    return import_run
