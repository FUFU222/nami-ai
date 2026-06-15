from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from nami_ai.config.spots import SurfSpot
from nami_ai.domain.schema import TimeWindow

JST = ZoneInfo("Asia/Tokyo")

RIDER_PROFILE = {
    "height_cm": 177,
    "weight_kg": 62,
    "board": "6'0 fish, 32L",
    "min_rideable": "腰",
    "preferences": ("サンセットセッションを好む", "潮が動く時間帯を優先"),
}


def parse_target_date(query: str, *, base_date: date | None = None) -> date:
    current = base_date or datetime.now(JST).date()
    if "明後日" in query or "あさって" in query:
        return current + timedelta(days=2)
    if "明日" in query or "あした" in query:
        return current + timedelta(days=1)
    if "今日" in query or "きょう" in query:
        return current

    date_match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", query)
    if date_match:
        year, month, day = (int(part) for part in date_match.groups())
        return date(year, month, day)

    for token in query.replace("/", "-").split():
        try:
            return date.fromisoformat(token)
        except ValueError:
            continue

    return current + timedelta(days=1)


def body_size_from_wave_height(wave_height_m: float) -> str:
    face_height = max(wave_height_m, 0.0) * 0.65
    if face_height < 0.12:
        return "flat"
    if face_height < 0.25:
        return "膝"
    if face_height < 0.42:
        return "腰"
    if face_height < 0.55:
        return "腹"
    if face_height < 0.68:
        return "胸"
    if face_height < 0.80:
        return "肩"
    if face_height < 1.00:
        return "頭"
    return "overhead"


def classify_swell(period_s: float) -> Literal["ground", "wind", "mixed"]:
    if period_s >= 8.0:
        return "ground"
    if period_s <= 6.0:
        return "wind"
    return "mixed"


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def classify_wind(spot: SurfSpot, *, wind_direction_deg: float, wind_speed_mps: float) -> str:
    if wind_speed_mps < 2.0:
        return "glassy"

    diff = _angle_diff(spot.offshore_dir, wind_direction_deg)
    if diff <= 45.0:
        return "offshore"
    if diff >= 135.0:
        return "onshore"
    return "cross"


def tide_movement_windows(tide: dict) -> list[TimeWindow]:
    events: list[tuple[int, str]] = []
    for event in tide.get("edd", []):
        events.append((_time_to_minutes(event["time"]), "干潮"))
    for event in tide.get("flood", []):
        events.append((_time_to_minutes(event["time"]), "満潮"))
    events.sort()

    windows: list[TimeWindow] = []
    for (start_min, start_type), (end_min, end_type) in zip(events, events[1:]):
        duration = end_min - start_min
        if duration <= 0:
            continue
        window_start = start_min + round(duration * 0.30)
        window_end = start_min + round(duration * 0.70)
        direction = "上げ潮" if start_type == "干潮" and end_type == "満潮" else "下げ潮"
        windows.append(
            TimeWindow(
                start=_minutes_to_time(window_start),
                end=_minutes_to_time(window_end),
                reason=f"{direction}の3〜7分で潮が動く時間帯",
            )
        )

    return windows


def recommend_sunset_window(sunset: str) -> TimeWindow:
    sunset_minutes = _time_to_minutes(_extract_hhmm(sunset))
    start = sunset_minutes - 120
    end = sunset_minutes - 90
    return TimeWindow(
        start=_minutes_to_time(start),
        end=_minutes_to_time(end),
        reason="サンセット前の1.5〜2時間で光量と風の落ち着きに期待",
    )


def _extract_hhmm(value: str) -> str:
    if "T" in value:
        return value.rsplit("T", 1)[1][:5]
    return value[:5]


def _time_to_minutes(hhmm: str) -> int:
    hour, minute = hhmm[:5].split(":")
    return int(hour) * 60 + int(minute)


def _minutes_to_time(minutes: int) -> str:
    minutes %= 24 * 60
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}"
