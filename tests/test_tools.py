from datetime import date, timedelta
import asyncio

from nami_ai.config.spots import get_spot
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
