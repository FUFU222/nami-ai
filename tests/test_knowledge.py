from datetime import date

from nami_ai.config.spots import get_spot
from nami_ai.domain.knowledge import (
    body_size_from_wave_height,
    classify_swell,
    classify_wind,
    parse_target_date,
    recommend_sunset_window,
    tide_movement_windows,
)


def test_parse_target_date_understands_today_and_tomorrow() -> None:
    base = date(2026, 6, 13)

    assert parse_target_date("明日の鵠沼どう？", base_date=base) == date(2026, 6, 14)
    assert parse_target_date("今日の辻堂どう？", base_date=base) == date(2026, 6, 13)


def test_wave_height_maps_to_shonan_body_size() -> None:
    assert body_size_from_wave_height(0.1) == "flat"
    assert body_size_from_wave_height(0.45) == "腰"
    assert body_size_from_wave_height(1.25) == "頭"


def test_swell_period_classification() -> None:
    assert classify_swell(8.0) == "ground"
    assert classify_swell(6.0) == "wind"
    assert classify_swell(7.0) == "mixed"


def test_wind_classification_uses_spot_offshore_direction() -> None:
    spot = get_spot("鵠沼")

    assert classify_wind(spot, wind_direction_deg=20.0, wind_speed_mps=4.0) == "offshore"
    assert classify_wind(spot, wind_direction_deg=90.0, wind_speed_mps=4.0) == "cross"
    assert classify_wind(spot, wind_direction_deg=205.0, wind_speed_mps=4.0) == "onshore"
    assert classify_wind(spot, wind_direction_deg=205.0, wind_speed_mps=1.0) == "glassy"


def test_tide_movement_windows_prefer_middle_of_tide_push() -> None:
    tide = {
        "flood": [{"time": "12:00", "cm": 120.0}],
        "edd": [{"time": "06:00", "cm": 20.0}],
    }

    windows = tide_movement_windows(tide)

    assert windows[0].start == "07:48"
    assert windows[0].end == "10:12"
    assert "上げ" in windows[0].reason


def test_sunset_window_starts_two_hours_before_sunset() -> None:
    window = recommend_sunset_window("18:56")

    assert window.start == "16:56"
    assert window.end == "17:26"
    assert "サンセット" in window.reason
