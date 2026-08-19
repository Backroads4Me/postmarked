from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.current_stop import (
    contains_today as _contains_today,
    is_live_current_stop as _is_live_current_stop,
    select_live_stop as _select_live_stop,
)


def _stop(*, start, end=None, is_current=False, stop_id="stop", sort_order=0):
    return SimpleNamespace(
        id=stop_id,
        start_date=datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
        end_date=datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc) if end else None,
        is_current=is_current,
        sort_order=sort_order,
    )


def test_live_when_stop_date_range_includes_today():
    today = date(2026, 8, 17)
    stop = _stop(start=date(2026, 8, 15), end=date(2026, 8, 20))

    assert _is_live_current_stop(stop, today) is True


def test_not_live_for_past_stop_without_is_current():
    today = date(2026, 8, 17)
    stop = _stop(start=date(2026, 8, 9), end=date(2026, 8, 12))

    assert _is_live_current_stop(stop, today) is False


def test_not_live_for_past_stop_with_stale_is_current():
    today = date(2026, 8, 17)
    stop = _stop(start=date(2026, 8, 9), end=date(2026, 8, 12), is_current=True)

    assert _is_live_current_stop(stop, today) is False


def test_live_for_open_ended_stop_with_is_current():
    today = date(2026, 8, 17)
    stop = _stop(start=date(2026, 8, 10), is_current=True)

    assert _is_live_current_stop(stop, today) is True


def test_live_for_open_ended_stop_without_is_current():
    today = date(2026, 8, 17)
    stop = _stop(start=date(2026, 8, 10))

    assert _contains_today(stop, today) is True
    assert _is_live_current_stop(stop, today) is True


def test_not_live_for_future_stop():
    today = date(2026, 8, 17)
    stop = _stop(start=date(2026, 8, 20), end=date(2026, 8, 25))

    assert _is_live_current_stop(stop, today) is False


def test_not_live_for_future_stop_with_stale_is_current():
    today = date(2026, 8, 17)
    stop = _stop(start=date(2026, 8, 20), end=date(2026, 8, 25), is_current=True)

    assert _is_live_current_stop(stop, today) is False


def test_live_on_end_date():
    today = date(2026, 8, 13)
    stop = _stop(start=date(2026, 8, 9), end=date(2026, 8, 13))

    assert _contains_today(stop, today) is True
    assert _is_live_current_stop(stop, today) is True


def test_select_live_stop_prefers_explicit_current_overlap():
    today = date(2026, 8, 19)
    explicit = _stop(
        start=date(2026, 8, 15),
        end=date(2026, 8, 21),
        is_current=True,
        stop_id="explicit",
        sort_order=1,
    )
    later = _stop(
        start=date(2026, 8, 18),
        end=date(2026, 8, 22),
        stop_id="later",
        sort_order=2,
    )

    assert _select_live_stop([later, explicit], today) is explicit


def test_select_live_stop_has_a_deterministic_overlap_fallback():
    today = date(2026, 8, 19)
    first = _stop(
        start=date(2026, 8, 18),
        end=date(2026, 8, 22),
        stop_id="first",
        sort_order=1,
    )
    second = _stop(
        start=date(2026, 8, 18),
        end=date(2026, 8, 22),
        stop_id="second",
        sort_order=2,
    )

    assert _select_live_stop([second, first], today) is second
