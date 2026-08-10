"""Tests for configurable weather temperature units."""
from unittest.mock import MagicMock, patch

import pytest

from app.services import weather


def test_invalid_unit_falls_back_to_fahrenheit(monkeypatch):
    monkeypatch.setenv("WEATHER_TEMPERATURE_UNIT", "kelvin")
    assert weather.weather_temperature_unit() == "fahrenheit"
    assert weather.weather_cache_key() == "weather:current:fahrenheit"


def test_cache_key_includes_configured_unit(monkeypatch):
    monkeypatch.setenv("WEATHER_TEMPERATURE_UNIT", "celsius")
    assert weather.weather_cache_key() == "weather:current:celsius"


def test_fahrenheit_to_unit_converts_and_rounds():
    assert weather._fahrenheit_to_unit(32, "celsius") == 0
    assert weather._fahrenheit_to_unit(212, "celsius") == 100
    assert weather._fahrenheit_to_unit(78.9, "celsius") == 26
    assert weather._fahrenheit_to_unit(79, "fahrenheit") == 79
    assert weather._fahrenheit_to_unit("bad", "fahrenheit", default=-999) == -999


@patch("app.services.weather.httpx.Client")
def test_fetch_weather_open_meteo_uses_configured_unit(mock_client_cls, monkeypatch):
    monkeypatch.setenv("WEATHER_TEMPERATURE_UNIT", "celsius")
    response = MagicMock()
    response.json.return_value = {
        "current": {"temperature_2m": 26.1, "weather_code": 3},
        "daily": {
            "weather_code": [3, 3, 3],
            "temperature_2m_max": [27, 28, 29],
            "temperature_2m_min": [18, 19, 20],
            "time": ["2026-08-10", "2026-08-11", "2026-08-12"],
        },
    }
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value = response
    mock_client_cls.return_value = client

    result = weather.fetch_weather(54.6872, 25.2797)

    assert result is not None
    assert result["unit"] == "celsius"
    assert result["current"]["temp"] == 26
    assert result["current"]["label"] == "Overcast"
    called_url = client.get.call_args[0][0]
    assert "temperature_unit=celsius" in called_url


@patch("app.services.weather.httpx.Client")
def test_fetch_weather_nws_converts_to_celsius(mock_client_cls, monkeypatch):
    monkeypatch.setenv("WEATHER_TEMPERATURE_UNIT", "celsius")
    client = MagicMock()
    client.__enter__.return_value = client

    def fake_get(url, *args, **kwargs):
        response = MagicMock()
        if url.endswith("/points/40.0,-105.0"):
            response.json.return_value = {
                "properties": {
                    "forecast": "https://api.weather.gov/gridpoints/BOU/63,75/forecast",
                    "forecastHourly": "https://api.weather.gov/gridpoints/BOU/63,75/forecast/hourly",
                }
            }
        elif url.endswith("/forecast/hourly"):
            response.json.return_value = {
                "properties": {
                    "periods": [{"temperature": 79, "shortForecast": "Sunny"}],
                }
            }
        else:
            response.json.return_value = {
                "properties": {
                    "periods": [
                        {"number": 1, "isDaytime": True, "temperature": 80, "shortForecast": "Sunny", "startTime": "2026-08-11T06:00:00-06:00"},
                        {"number": 2, "isDaytime": False, "temperature": 55, "shortForecast": "Clear", "startTime": "2026-08-11T18:00:00-06:00"},
                        {"number": 3, "isDaytime": True, "temperature": 82, "shortForecast": "Hot", "startTime": "2026-08-12T06:00:00-06:00"},
                        {"number": 4, "isDaytime": False, "temperature": 58, "shortForecast": "Clear", "startTime": "2026-08-12T18:00:00-06:00"},
                    ],
                }
            }
        return response

    client.get.side_effect = fake_get
    mock_client_cls.return_value = client

    with patch.object(weather, "_fetch_open_meteo", return_value=None):
        result = weather.fetch_weather(40.0, -105.0)

    assert result is not None
    assert result["unit"] == "celsius"
    assert result["current"]["temp"] == 26
    assert result["forecast"][0]["high"] == 28


@pytest.mark.live
def test_live_fetch_vilnius_units_agree(monkeypatch):
    """Opt-in: prove the unit param reaches Open-Meteo without seasonal bounds."""
    lat, lon = 54.6872, 25.2797
    monkeypatch.setenv("WEATHER_TEMPERATURE_UNIT", "celsius")
    celsius_result = weather.fetch_weather(lat, lon)
    monkeypatch.setenv("WEATHER_TEMPERATURE_UNIT", "fahrenheit")
    fahrenheit_result = weather.fetch_weather(lat, lon)

    assert celsius_result is not None
    assert fahrenheit_result is not None
    assert celsius_result["unit"] == "celsius"
    assert fahrenheit_result["unit"] == "fahrenheit"

    celsius_temp = celsius_result["current"]["temp"]
    fahrenheit_temp = fahrenheit_result["current"]["temp"]
    expected_f = round(celsius_temp * 9 / 5 + 32)
    assert abs(fahrenheit_temp - expected_f) <= 1
