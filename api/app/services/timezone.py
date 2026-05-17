from typing import Optional
from timezonefinder import TimezoneFinder

_tf = TimezoneFinder()


def timezone_for_coords(lat: float, lon: float) -> Optional[str]:
    return _tf.timezone_at(lat=lat, lng=lon)
