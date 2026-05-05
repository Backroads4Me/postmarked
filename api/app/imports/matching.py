"""
Import matching and diff logic.

Compares incoming parsed stops against existing planned stops
to produce a preview diff before applying changes.
"""
import math
from typing import Optional
from app.imports.rv_trip_wizard import ParsedStop, normalize_name


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance between two lat/lon points in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def name_similarity(a: str, b: str) -> float:
    """Simple normalized name similarity (0-1)."""
    na, nb = normalize_name(a), normalize_name(b)
    if na == nb:
        return 1.0
    # Check if one contains the other
    if na in nb or nb in na:
        return 0.8
    # Word overlap
    wa, wb = set(na.split()), set(nb.split())
    if not wa or not wb:
        return 0.0
    overlap = len(wa & wb)
    return overlap / max(len(wa), len(wb))


def find_exact_match(incoming: ParsedStop, existing: list) -> Optional[dict]:
    """Find an exact fingerprint match in existing planned stops."""
    for ex in existing:
        if ex.get("source_fingerprint") == incoming.fingerprint:
            return ex
    return None


def find_fuzzy_match(incoming: ParsedStop, existing: list, threshold_meters: float = 150.0) -> Optional[dict]:
    """
    Find a fuzzy match using:
    - Coordinates within threshold_meters
    - Similar normalized stop name
    - Arrival/departure within 3 days
    """
    candidates = []
    for ex in existing:
        score = 0.0

        # Name similarity
        ns = name_similarity(incoming.name, ex.get("name", ""))
        if ns < 0.5:
            continue
        score += ns * 40

        # Coordinate proximity
        if incoming.latitude and incoming.longitude and ex.get("latitude") and ex.get("longitude"):
            dist = haversine_meters(incoming.latitude, incoming.longitude, ex["latitude"], ex["longitude"])
            if dist <= threshold_meters:
                score += 30
            elif dist <= 500:
                score += 15
            else:
                continue  # Too far

        # Date proximity
        if incoming.arrival_date and ex.get("arrival_date"):
            from datetime import date
            ex_arrival = ex["arrival_date"] if isinstance(ex["arrival_date"], date) else None
            if ex_arrival:
                day_diff = abs((incoming.arrival_date - ex_arrival).days)
                if day_diff <= 3:
                    score += 20
                elif day_diff <= 7:
                    score += 10

        if score >= 60:
            candidates.append((ex, score))

    if len(candidates) == 1:
        return candidates[0][0]
    elif len(candidates) > 1:
        # Multiple matches — return highest score but flag as needs_review
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    return None


def compute_field_changes(incoming: ParsedStop, existing: dict) -> list[str]:
    """Compare fields and return list of changed field names."""
    changes = []
    compare_fields = [
        ("name", "name"),
        ("arrival_date", "arrival_date"),
        ("departure_date", "departure_date"),
        ("nights", "nights"),
        ("latitude", "latitude"),
        ("longitude", "longitude"),
        ("address", "address"),
        ("features_raw", "features_raw"),
        ("miles_from_previous", "miles_from_previous"),
        ("total_miles", "total_miles"),
        ("estimated_travel_time", "estimated_travel_time"),
    ]
    for incoming_field, existing_field in compare_fields:
        incoming_val = getattr(incoming, incoming_field, None)
        existing_val = existing.get(existing_field)
        if incoming_val != existing_val:
            changes.append(incoming_field)
    return changes


def is_dangerous_change(changes: list[str], existing: dict) -> bool:
    """Check if any change is dangerous (linked to lived content)."""
    dangerous_fields = {"latitude", "longitude", "arrival_date", "departure_date"}
    has_lived_link = existing.get("matched_stop_id") is not None
    return has_lived_link and bool(dangerous_fields & set(changes))


def diff_import(incoming_stops: list[ParsedStop], existing_planned: list[dict]) -> list[dict]:
    """
    Produce a diff preview comparing incoming parsed stops against existing planned stops.

    Returns list of diff items with status: added, unchanged, changed, removed, needs_review
    """
    diff = []
    matched_ids = set()

    for stop in incoming_stops:
        # Try exact match
        match = find_exact_match(stop, existing_planned)
        if match:
            matched_ids.add(match["id"])
            changes = compute_field_changes(stop, match)
            if not changes:
                diff.append({
                    "status": "unchanged",
                    "sequence": stop.sequence,
                    "name": stop.name,
                    "arrival_date": stop.arrival_date,
                    "departure_date": stop.departure_date,
                    "nights": stop.nights,
                    "miles": stop.miles_from_previous,
                    "existing_id": match["id"],
                    "changes": [],
                    "is_dangerous": False,
                })
            else:
                dangerous = is_dangerous_change(changes, match)
                diff.append({
                    "status": "needs_review" if dangerous else "changed",
                    "sequence": stop.sequence,
                    "name": stop.name,
                    "arrival_date": stop.arrival_date,
                    "departure_date": stop.departure_date,
                    "nights": stop.nights,
                    "miles": stop.miles_from_previous,
                    "existing_id": match["id"],
                    "changes": changes,
                    "is_dangerous": dangerous,
                })
            continue

        # Try fuzzy match
        fuzzy = find_fuzzy_match(stop, [e for e in existing_planned if e["id"] not in matched_ids])
        if fuzzy:
            matched_ids.add(fuzzy["id"])
            changes = compute_field_changes(stop, fuzzy)
            dangerous = is_dangerous_change(changes, fuzzy)
            diff.append({
                "status": "needs_review" if len([e for e in existing_planned if e["id"] not in matched_ids]) > 0 else "changed",
                "sequence": stop.sequence,
                "name": stop.name,
                "arrival_date": stop.arrival_date,
                "departure_date": stop.departure_date,
                "nights": stop.nights,
                "miles": stop.miles_from_previous,
                "existing_id": fuzzy["id"],
                "changes": changes,
                "is_dangerous": dangerous,
            })
            continue

        # No match — new stop
        diff.append({
            "status": "added",
            "sequence": stop.sequence,
            "name": stop.name,
            "arrival_date": stop.arrival_date,
            "departure_date": stop.departure_date,
            "nights": stop.nights,
            "miles": stop.miles_from_previous,
            "existing_id": None,
            "changes": [],
            "is_dangerous": False,
        })

    # Check for removed stops
    for ex in existing_planned:
        if ex["id"] not in matched_ids:
            diff.append({
                "status": "removed",
                "sequence": 0,
                "name": ex.get("name", "Unknown"),
                "arrival_date": ex.get("arrival_date"),
                "departure_date": ex.get("departure_date"),
                "nights": ex.get("nights"),
                "miles": None,
                "existing_id": ex["id"],
                "changes": [],
                "is_dangerous": ex.get("matched_stop_id") is not None,
            })

    return diff
