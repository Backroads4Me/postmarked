from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.routers.journey import _contains_today, _is_live_current_stop


def _stop(*, start, end=None, is_current=False):
    return SimpleNamespace(
        start_date=datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
        end_date=datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc) if end else None,
        is_current=is_current,
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
