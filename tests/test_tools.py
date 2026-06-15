from datetime import date, timedelta
import asyncio

import httpx

from nami_ai.config.spots import get_spot
from nami_ai.tools import marine, tide, weather
from nami_ai.tools.marine import fetch_marine_forecast
from nami_ai.tools.tide import fetch_tide
from nami_ai.tools.weather import fetch_weather_forecast


def _tomorrow() -> date:
    return date.today() + timedelta(days=1)


def test_marine_tool_fetches_and_trims_live_open_meteo_data() -> None:
    spot = get_spot("鵠沼")
    target_date = _tomorrow()

    data = asyncio.run(fetch_marine_forecast(spot, target_date))

    assert data["spot"] == "鵠沼"
    assert data["date"] == target_date.isoformat()
    assert data["hours"]
    assert all(5 <= int(hour["time"][:2]) <= 18 for hour in data["hours"])
    assert {"time", "wave_height_m", "wave_direction_deg", "wave_period_s"} <= set(data["hours"][0])


def test_weather_tool_fetches_wind_and_sun_live_open_meteo_data() -> None:
    spot = get_spot("辻堂")
    target_date = _tomorrow()

    data = asyncio.run(fetch_weather_forecast(spot, target_date))

    assert data["spot"] == "辻堂"
    assert data["date"] == target_date.isoformat()
    assert data["sunrise"]
    assert data["sunset"]
    assert data["hours"]
    assert {"time", "wind_speed_mps", "wind_direction_deg", "temperature_c"} <= set(data["hours"][0])


def test_tide_tool_fetches_enoshima_tide736_data() -> None:
    target_date = _tomorrow()

    data = asyncio.run(fetch_tide(target_date))

    assert data["date"] == target_date.isoformat()
    assert data["reference"] == "江ノ島"
    assert data["flood"] or data["edd"]
    if data["flood"]:
        assert isinstance(data["flood"][0]["cm"], float)
        assert round(data["flood"][0]["cm"], 1) == data["flood"][0]["cm"]


def test_marine_tool_wraps_http_failures(monkeypatch) -> None:
    monkeypatch.setattr(marine.httpx, "AsyncClient", _failing_async_client)

    try:
        asyncio.run(fetch_marine_forecast(get_spot("鵠沼"), _tomorrow()))
    except RuntimeError as exc:
        assert "Marine API request failed" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_weather_tool_wraps_http_failures(monkeypatch) -> None:
    monkeypatch.setattr(weather.httpx, "AsyncClient", _failing_async_client)

    try:
        asyncio.run(fetch_weather_forecast(get_spot("辻堂"), _tomorrow()))
    except RuntimeError as exc:
        assert "Weather API request failed" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_tide_tool_wraps_http_failures(monkeypatch) -> None:
    monkeypatch.setattr(tide.httpx, "AsyncClient", _failing_async_client)

    try:
        asyncio.run(fetch_tide(_tomorrow()))
    except RuntimeError as exc:
        assert "Tide API request failed" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_tide_tool_rejects_chart_without_target_date(monkeypatch) -> None:
    monkeypatch.setattr(
        tide.httpx,
        "AsyncClient",
        lambda **kwargs: _json_async_client(
            {
                "tide": {
                    "chart": {
                        "2026-06-21": {
                            "flood": [],
                            "edd": [],
                            "sun": {},
                            "moon": {"title": "中潮"},
                        }
                    }
                }
            }
        ),
    )

    try:
        asyncio.run(fetch_tide(date(2026, 6, 20)))
    except RuntimeError as exc:
        assert "no chart data for 2026-06-20" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_tide_tool_wraps_malformed_tide_event(monkeypatch) -> None:
    monkeypatch.setattr(
        tide.httpx,
        "AsyncClient",
        lambda **kwargs: _json_async_client(
            {
                "tide": {
                    "chart": {
                        "2026-06-20": {
                            "flood": [{"time": "12:00", "unix": 1}],
                            "edd": [],
                            "sun": {},
                            "moon": {"title": "中潮"},
                        }
                    }
                }
            }
        ),
    )

    try:
        asyncio.run(fetch_tide(date(2026, 6, 20)))
    except RuntimeError as exc:
        assert "malformed tide event" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def _failing_async_client(**kwargs):
    return _FailingAsyncClient()


def _json_async_client(payload: dict):
    return _JsonAsyncClient(payload)


class _FailingAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        raise httpx.ConnectError("network unavailable")


class _JsonAsyncClient:
    def __init__(self, payload: dict):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return _JsonResponse(self.payload)


class _JsonResponse:
    status_code = 200

    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload
