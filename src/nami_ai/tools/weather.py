from __future__ import annotations

from datetime import date
from statistics import fmean
from typing import Any

import httpx

from nami_ai.config.spots import SurfSpot

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_HOURLY = ("wind_speed_10m", "wind_direction_10m", "temperature_2m")
WEATHER_DAILY = ("sunrise", "sunset")


async def fetch_weather_forecast(spot: SurfSpot, target_date: date) -> dict[str, Any]:
    params = {
        "latitude": spot.lat,
        "longitude": spot.lon,
        "hourly": ",".join(WEATHER_HOURLY),
        "daily": ",".join(WEATHER_DAILY),
        "timezone": "Asia/Tokyo",
        "wind_speed_unit": "ms",
        "temperature_unit": "celsius",
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(WEATHER_API_URL, params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Weather API request failed: {exc}") from exc

    payload = response.json()
    hourly = payload.get("hourly")
    daily = payload.get("daily")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise RuntimeError("Weather API response did not include hourly time series")
    if not isinstance(daily, dict):
        raise RuntimeError("Weather API response did not include daily sun data")

    hours = _trim_weather_hours(hourly, target_date)
    if not hours:
        raise RuntimeError(f"Weather API returned no usable hourly data for {target_date.isoformat()}")

    wind_speeds = [hour["wind_speed_mps"] for hour in hours if hour["wind_speed_mps"] is not None]
    return {
        "source": "open-meteo-weather",
        "spot": spot.name,
        "date": target_date.isoformat(),
        "timezone": "Asia/Tokyo",
        "sunrise": _extract_hhmm(_first(daily.get("sunrise"))),
        "sunset": _extract_hhmm(_first(daily.get("sunset"))),
        "hours": hours,
        "summary": {
            "avg_wind_speed_mps": _round(fmean(wind_speeds)) if wind_speeds else None,
            "max_wind_speed_mps": _round(max(wind_speeds)) if wind_speeds else None,
        },
    }


def _trim_weather_hours(hourly: dict[str, list[Any]], target_date: date) -> list[dict[str, Any]]:
    hours: list[dict[str, Any]] = []
    for idx, timestamp in enumerate(hourly["time"]):
        day, hhmm = timestamp.split("T", 1)
        hour = int(hhmm[:2])
        if day != target_date.isoformat() or not 5 <= hour <= 18:
            continue
        hours.append(
            {
                "time": hhmm[:5],
                "wind_speed_mps": _round(_value(hourly, "wind_speed_10m", idx)),
                "wind_direction_deg": _round(_value(hourly, "wind_direction_10m", idx)),
                "temperature_c": _round(_value(hourly, "temperature_2m", idx)),
            }
        )
    return hours


def _first(values: list[Any] | None) -> str | None:
    if not values:
        return None
    return values[0]


def _extract_hhmm(value: str | None) -> str | None:
    if value is None:
        return None
    if "T" in value:
        return value.rsplit("T", 1)[1][:5]
    return value[:5]


def _value(hourly: dict[str, list[Any]], key: str, idx: int) -> float | None:
    values = hourly.get(key, [])
    if idx >= len(values):
        return None
    value = values[idx]
    return float(value) if value is not None else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None
