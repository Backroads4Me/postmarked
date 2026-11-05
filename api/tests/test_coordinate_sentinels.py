"""The stop-page map centers on the stop's coordinates, so a placeholder
coordinate became a map of the Gulf of Guinea.

RV Trip Wizard writes -1 into latitude/longitude cells it could not resolve,
and -1 passes every range check; the Foretravel Rally import shipped with
stops parked at (-1, -1) and (0, -1). The parser drops placeholder pairs as
missing, and public coordinate reads report them as no location so map
surfaces hide instead of centering on the ocean.
"""

import openpyxl

from app.imports.rv_trip_wizard import parse_excel
from app.services.coordinates import usable_coordinates


def _workbook(tmp_path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Trip Summary"
    ws.cell(row=1, column=1, value="Foretravel Rally - 2026")
    ws.cell(row=2, column=1, value="10/01/26")
    for col, name in enumerate(("Stop Name", "Latitude", "Longitude"), start=1):
        ws.cell(row=4, column=col, value=name)
    for offset, (name, lat, lon) in enumerate(rows):
        ws.cell(row=5 + offset, column=1, value=name)
        if lat is not None:
            ws.cell(row=5 + offset, column=2, value=lat)
        if lon is not None:
            ws.cell(row=5 + offset, column=3, value=lon)
    path = tmp_path / "trip.xlsx"
    wb.save(path)
    return str(path)


def test_wizard_placeholder_pairs_parse_as_no_location(tmp_path):
    path = _workbook(
        tmp_path,
        [
            ("The Ridge Outdoor Resort", -1, -1),
            ("Brushy Mountain State Penitentiary", 0, -1),
            ("Real Campground", 35.8412592, -83.5405319),
        ],
    )

    parsed = parse_excel(path)
    by_name = {stop.name: stop for stop in parsed.stops}

    ridge = by_name["The Ridge Outdoor Resort"]
    assert (ridge.latitude, ridge.longitude) == (None, None)

    # A lone -1 longitude must not leave a half pair behind.
    brushy = by_name["Brushy Mountain State Penitentiary"]
    assert (brushy.latitude, brushy.longitude) == (None, None)

    real = by_name["Real Campground"]
    assert (real.latitude, real.longitude) == (35.8412592, -83.5405319)


def test_stops_without_coordinates_are_warned(tmp_path):
    path = _workbook(
        tmp_path,
        [
            ("The Ridge Outdoor Resort", -1, -1),
            ("Real Campground", 35.84, -83.54),
        ],
    )

    parsed = parse_excel(path)

    assert any(
        "The Ridge Outdoor Resort" in w and "coordinates" in w
        for w in parsed.warnings
    )
    assert not any("Real Campground" in w for w in parsed.warnings)


def test_blank_coordinate_cells_parse_as_no_location(tmp_path):
    path = _workbook(tmp_path, [("Blank Campground", None, None)])

    parsed = parse_excel(path)

    stop = parsed.stops[0]
    assert (stop.latitude, stop.longitude) == (None, None)


def test_placeholder_pairs_report_no_location_on_read():
    assert usable_coordinates(-1.0, -1.0) == (None, None)
    assert usable_coordinates(0.0, -1.0) == (None, None)
    assert usable_coordinates(-1.0, 35.84) == (None, None)
    assert usable_coordinates(35.8412592, -83.5405319) == (35.8412592, -83.5405319)


def test_absent_and_non_finite_coordinates_report_no_location():
    assert usable_coordinates(None, -83.5) == (None, None)
    assert usable_coordinates(35.8, None) == (None, None)
    assert usable_coordinates(float("nan"), -83.5) == (None, None)
    assert usable_coordinates(35.8, float("inf")) == (None, None)
