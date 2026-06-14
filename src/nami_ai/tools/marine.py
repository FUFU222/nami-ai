from __future__ import annotations

from datetime import date
from statistics import fmean
from typing import Any

import httpx

from nami_ai.config.spots import SurfSpot

MARINE_API_URL = "https://api.open-meteo.com/v1/marine"
MARINE_API_FALLBACK_URL = "https://marine-api.open-meteo.com/v1/marine"
MARINE_HOURLY = (
    "wave_height",
    "wave_direction",
    "wave_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
    "swell_wave_peak_period",
)


async def fetch_marine_forecast(spot: SurfSpot, target_date: date) -> dict[str, Any]:
    params = {
        "latitude": spot.lat,
        "longitude": spot.lon,
        "hourly": ",".join(MARINE_HOURLY),
        "timezone": "Asia/Tokyo",
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(MARINE_API_URL, params=params)
            if response.status_code == 404:
                response = await client.get(MARINE_API_FALLBACK_URL, params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Marine API request failed: {exc}") from exc

    payload = response.json()
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise RuntimeError("Marine API response did not include hourly time series")

    hours = _trim_marine_hours(hourly, target_date)
    if not hours:
        raise RuntimeError(f"Marine API returned no usable hourly data for {target_date.isoformat()}")

    wave_heights = [hour["wave_height_m"] for hour in hours if hour["wave_height_m"] is not None]
    swell_periods = [hour["swell_period_s"] for hour in hours if hour["swell_period_s"] is not None]

    return {
        "source": "open-meteo-marine",
        "spot": spot.name,
        "date": target_date.isoformat(),
        "timezone": "Asia/Tokyo",
        "hours": hours,
        "summary": {
            "max_wave_height_m": _round(max(wave_heights)) if wave_heights else None,
            "avg_wave_height_m": _round(fmean(wave_heights)) if wave_heights else None,
            "avg_swell_period_s": _round(fmean(swell_periods)) if swell_periods else None,
        },
    }


def _trim_marine_hours(hourly: dict[str, list[Any]], target_date: date) -> list[dict[str, Any]]:
    hours: list[dict[str, Any]] = []
    for idx, timestamp in enumerate(hourly["time"]):
        day, hhmm = timestamp.split("T", 1)
        hour = int(hhmm[:2])
        if day != target_date.isoformat() or not 5 <= hour <= 18:
            continue

        wave_period = _value(hourly, "wave_period", idx)
        swell_period = (
            _value(hourly, "swell_wave_peak_period", idx)
            or _value(hourly, "swell_wave_period", idx)
            or wave_period
        )
        hours.append(
            {
                "time": hhmm[:5],
                "wave_height_m": _round(_value(hourly, "wave_height", idx)),
                "wave_direction_deg": _round(_value(hourly, "wave_direction", idx)),
                "wave_period_s": _round(wave_period),
                "swell_wave_height_m": _round(_value(hourly, "swell_wave_height", idx)),
                "swell_direction_deg": _round(_value(hourly, "swell_wave_direction", idx)),
                "swell_period_s": _round(swell_period),
            }
        )
    return hours


def _value(hourly: dict[str, list[Any]], key: str, idx: int) -> float | None:
    values = hourly.get(key, [])
    if idx >= len(values):
        return None
    value = values[idx]
    return float(value) if value is not None else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None
