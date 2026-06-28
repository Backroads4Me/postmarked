"""Weather fetching and caching.

Weather for the current stop is refreshed out-of-band by the ``refresh_weather``
Celery beat task and cached in Redis, so public page renders (``/api/home``)
read a cached value instead of making a blocking external API call on every
request. See api/app/tasks.py for the scheduler entry.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Cached, ready-to-serve weather payload for the current stop.
WEATHER_CACHE_KEY = "weather:current"
# Coordinates of the current stop, written by /api/home so the scheduled task
# knows where to fetch weather for without re-deriving the current stop.
WEATHER_COORDS_KEY = "weather:coords"
# TTL is longer than the refresh interval so a single missed run doesn't blank
# the homepage; a stale-but-present reading beats no reading.
WEATHER_TTL_SECONDS = int(os.getenv("WEATHER_TTL_SECONDS", str(3 * 60 * 60)))

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "contact@example.com")
_NWS_USER_AGENT = f"postmarked-app/1.0 ({ADMIN_EMAIL})"

# WMO weather interpretation codes -> human labels (mirrors web/src/lib/weather.js)
WMO_CODES = {
    0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    56: "Light Freezing Drizzle", 57: "Freezing Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    66: "Light Freezing Rain", 67: "Freezing Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow", 77: "Snow Grains",
    80: "Light Showers", 81: "Showers", 82: "Heavy Showers",
    85: "Light Snow Showers", 86: "Snow Showers",
    95: "Thunderstorm", 96: "T-storm w/ Hail", 99: "T-storm w/ Hail",
}


def _round(value, default=0) -> int:
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return default


def _fetch_open_meteo(lat: float, lon: float) -> Optional[dict]:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code,is_day"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        "&timezone=auto&forecast_days=3&temperature_unit=fahrenheit"
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(url)
            res.raise_for_status()
            data = res.json()
    except Exception as exc:  # noqa: BLE001 - external call, fail soft
        logger.warning("Open-Meteo weather fetch failed: %s", exc)
        return None

    current = data.get("current") or {}
    daily = data.get("daily") or {}
    forecast = []
    for i in (1, 2):
        codes = daily.get("weather_code") or []
        highs = daily.get("temperature_2m_max") or []
        lows = daily.get("temperature_2m_min") or []
        times = daily.get("time") or []
        code = codes[i] if i < len(codes) else None
        forecast.append(
            {
                "day": _weekday(times[i]) if i < len(times) else "",
                "high": _round(highs[i]) if i < len(highs) else 0,
                "low": _round(lows[i]) if i < len(lows) else 0,
                "label": WMO_CODES.get(code, "Unknown"),
            }
        )

    return {
        "current": {
            "temp": _round(current.get("temperature_2m")),
            "label": WMO_CODES.get(current.get("weather_code"), "Unknown"),
        },
        "forecast": forecast,
    }


def _fetch_nws(lat: float, lon: float) -> Optional[dict]:
    headers = {"User-Agent": _NWS_USER_AGENT}
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            points = client.get(f"https://api.weather.gov/points/{lat},{lon}")
            points.raise_for_status()
            props = (points.json() or {}).get("properties") or {}
            forecast_url = props.get("forecast")
            hourly_url = props.get("forecastHourly")
            if not forecast_url or not hourly_url:
                return None

            daily = client.get(forecast_url)
            hourly = client.get(hourly_url)
            daily.raise_for_status()
            hourly.raise_for_status()
            daily_periods = (daily.json().get("properties") or {}).get("periods") or []
            hourly_periods = (hourly.json().get("properties") or {}).get("periods") or []
    except Exception as exc:  # noqa: BLE001 - external call, fail soft
        logger.warning("NWS weather fetch failed: %s", exc)
        return None

    if not hourly_periods:
        return None
    current_period = hourly_periods[0]

    daytime = [p for p in daily_periods if p.get("isDaytime")][1:3]
    forecast = []
    for p in daytime:
        night = next(
            (n for n in daily_periods if not n.get("isDaytime") and n.get("number") == p.get("number", 0) + 1),
            None,
        )
        forecast.append(
            {
                "day": _weekday_iso(p.get("startTime")),
                "high": p.get("temperature", 0),
                "low": (night or {}).get("temperature", p.get("temperature", 0) - 15),
                "label": p.get("shortForecast", ""),
            }
        )

    return {
        "current": {
            "temp": current_period.get("temperature", 0),
            "label": current_period.get("shortForecast", ""),
        },
        "forecast": forecast,
    }


def _weekday(date_str: Optional[str]) -> str:
    from datetime import datetime

    if not date_str:
        return ""
    try:
        return datetime.fromisoformat(f"{date_str}T12:00:00").strftime("%a")
    except ValueError:
        return ""


def _weekday_iso(iso_str: Optional[str]) -> str:
    from datetime import datetime

    if not iso_str:
        return ""
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%a")
    except ValueError:
        return ""


def fetch_weather(lat: float, lon: float) -> Optional[dict]:
    """Fetch weather for a coordinate, Open-Meteo first with NWS as fallback."""
    return _fetch_open_meteo(lat, lon) or _fetch_nws(lat, lon)
