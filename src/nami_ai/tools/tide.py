from __future__ import annotations

from datetime import date
from typing import Any

import httpx

TIDE_API_URL = "https://api.tide736.net/get_tide.php"


async def fetch_tide(target_date: date) -> dict[str, Any]:
    params = {
        "pc": 14,
        "hc": 19,
        "yr": target_date.year,
        "mn": target_date.month,
        "dy": target_date.day,
        "rg": "day",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(TIDE_API_URL, params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Tide API request failed: {exc}") from exc

    payload = response.json()
    try:
        chart = payload["tide"]["chart"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Tide API response did not include tide.chart") from exc

    day_payload = chart.get(target_date.isoformat())
    if not isinstance(day_payload, dict):
        raise RuntimeError(f"Tide API returned no chart data for {target_date.isoformat()}")

    moon = day_payload.get("moon") or {}
    return {
        "source": "tide736",
        "reference": "江ノ島",
        "date": target_date.isoformat(),
        "tide_name": moon.get("title"),
        "flood": [_normalize_tide_event(event) for event in day_payload.get("flood", [])],
        "edd": [_normalize_tide_event(event) for event in day_payload.get("edd", [])],
        "sun": day_payload.get("sun") or {},
        "moon": moon,
    }


def _normalize_tide_event(event: dict[str, Any]) -> dict[str, Any]:
    try:
        return {
            "time": str(event.get("time", ""))[:5],
            "cm": round(float(event["cm"]), 1),
            "unix": int(event["unix"]) if event.get("unix") is not None else None,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Tide API returned malformed tide event: {event}") from exc
