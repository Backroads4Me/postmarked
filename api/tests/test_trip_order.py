from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.trip_order import order_trips_newest_first


def _dt(year, month, day):
    return datetime(year, month, day, tzinfo=UTC)


def _trip(trip_id, start=None, end=None):
    return SimpleNamespace(id=trip_id, start_date=start, end_date=end)


def _stop(trip_id, start, end=None):
    return SimpleNamespace(trip_id=trip_id, start_date=start, end_date=end)


def _ids(pairs):
    return [trip.id for trip, _ in pairs]


def test_dated_trips_sort_newest_first():
    trips = [_trip("old", _dt(2024, 5, 1)), _trip("new", _dt(2026, 5, 1))]

    assert _ids(order_trips_newest_first(trips, [])) == ["new", "old"]


def test_trip_without_dates_sorts_by_its_stops():
    trips = [_trip("dated", _dt(2025, 1, 1)), _trip("from-stops")]
    stops = [_stop("from-stops", _dt(2026, 8, 20)), _stop("from-stops", _dt(2026, 8, 10))]

    assert _ids(order_trips_newest_first(trips, stops)) == ["from-stops", "dated"]


def test_trip_end_date_is_used_when_start_date_is_missing():
    trips = [_trip("dated", _dt(2025, 1, 1)), _trip("end-only", end=_dt(2026, 1, 1))]

    assert _ids(order_trips_newest_first(trips, [])) == ["end-only", "dated"]


def test_undated_trips_sort_last_in_a_stable_order():
    trips = [_trip("a"), _trip("dated", _dt(2020, 1, 1)), _trip("b")]

    first = _ids(order_trips_newest_first(trips, []))
    again = _ids(order_trips_newest_first(list(reversed(trips)), []))

    assert first == ["dated", "b", "a"]
    assert again == first


def test_same_date_trips_break_ties_on_id():
    same = _dt(2026, 3, 1)
    trips = [_trip("a", same), _trip("b", same)]

    assert _ids(order_trips_newest_first(trips, [])) == _ids(order_trips_newest_first(trips[::-1], []))


def test_each_trip_is_paired_with_only_its_stops():
    trips = [_trip("t1"), _trip("t2")]
    s1, s2 = _stop("t1", _dt(2026, 1, 1)), _stop("t2", _dt(2026, 2, 1))

    pairs = {trip.id: stops for trip, stops in order_trips_newest_first(trips, [s1, s2])}

    assert pairs == {"t1": [s1], "t2": [s2]}
