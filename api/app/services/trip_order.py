from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime


def trip_effective_start(trip, stops: Iterable) -> datetime | None:
    """Start of the date range the trips page shows for a trip.

    Mirrors ``tripDateRange`` in web/src/pages/trips/index.astro: the trip's own
    dates win, otherwise the earliest date among its stops.
    """
    if trip.start_date or trip.end_date:
        return trip.start_date or trip.end_date
    dates = [s.start_date or s.end_date for s in stops if s.start_date or s.end_date]
    return min(dates) if dates else None


def order_trips_newest_first[T](trips: Iterable[T], stops: Iterable) -> list[tuple[T, list]]:
    """Pair each trip with its stops, newest effective start first.

    Undated trips sort last; ties break on trip id so the order is stable.
    """
    stops_by_trip = defaultdict(list)
    for stop in stops:
        stops_by_trip[stop.trip_id].append(stop)

    def key(pair):
        trip, trip_stops = pair
        start = trip_effective_start(trip, trip_stops)
        return (start is not None, start or datetime.min.replace(tzinfo=UTC), str(trip.id))

    pairs = [(trip, stops_by_trip[trip.id]) for trip in trips]
    return sorted(pairs, key=key, reverse=True)
