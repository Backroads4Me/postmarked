
from timezonefinder import TimezoneFinder

_tf = TimezoneFinder()


def timezone_for_coords(lat: float, lon: float) -> str | None:
    return _tf.timezone_at(lat=lat, lng=lon)
