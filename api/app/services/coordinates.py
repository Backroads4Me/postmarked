"""Guards for stop coordinates read out of the PostGIS geometry columns."""

import math

# RV Trip Wizard writes -1 into coordinate cells it could not resolve, and
# -1 is an in-range degree value, so range checks alone let the placeholder
# reach the database as a POINT in the Gulf of Guinea. A stop whose latitude
# or longitude is exactly -1 has no usable location; reads report it as
# missing so map surfaces hide instead of centering on the ocean.
MISSING_COORDINATE = -1.0


def usable_coordinates(
    lat: float | None, lon: float | None
) -> tuple[float | None, float | None]:
    """Return (lat, lon), or (None, None) when the point is absent or a placeholder."""
    if lat is None or lon is None:
        return (None, None)
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return (None, None)
    if lat == MISSING_COORDINATE or lon == MISSING_COORDINATE:
        return (None, None)
    return (lat, lon)
