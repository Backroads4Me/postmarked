from datetime import date
from typing import Iterable, TypeVar


StopT = TypeVar("StopT")


def contains_today(stop, today: date) -> bool:
    start = stop.start_date.date() if stop.start_date else None
    if not start:
        return False
    if not stop.end_date:
        return start <= today
    return start <= today <= stop.end_date.date()


def is_live_current_stop(stop, today: date) -> bool:
    if contains_today(stop, today):
        return True
    if not stop.is_current:
        return False

    start = stop.start_date.date() if stop.start_date else None
    if start and start > today:
        return False
    end = stop.end_date.date() if stop.end_date else None
    return end is None or end >= today


def _selection_key(stop) -> tuple[date, int, str]:
    start = stop.start_date.date() if stop.start_date else date.min
    sort_order = stop.sort_order if isinstance(stop.sort_order, int) else -1
    identity = str(getattr(stop, "id", None) or getattr(stop, "slug", ""))
    return start, sort_order, identity


def select_live_stop(stops: Iterable[StopT], today: date) -> StopT | None:
    """Select one live stop, preferring an explicit marker before route order."""
    live = [stop for stop in stops if is_live_current_stop(stop, today)]
    explicit = [stop for stop in live if stop.is_current]
    candidates = explicit or live
    return max(candidates, key=_selection_key, default=None)
