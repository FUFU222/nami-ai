from datetime import date

from nami_ai.agent.forecaster import build_heuristic_forecast
from nami_ai.config.spots import get_spot


def test_heuristic_forecast_returns_structured_surf_forecast() -> None:
    spot = get_spot("辻堂")
    raw_data = {
        "marine": {
            "hours": [
                {
                    "time": "16:00",
                    "wave_height_m": 0.62,
                    "swell_period_s": 7.5,
                    "swell_direction_deg": 180.0,
                }
            ]
        },
        "weather": {
            "sunset": "18:56",
            "hours": [
                {
                    "time": "16:00",
                    "wind_speed_mps": 1.5,
                    "wind_direction_deg": 210.0,
                    "temperature_c": 24.0,
                }
            ],
        },
        "tide": {
            "tide_name": "大潮",
            "flood": [{"time": "12:00", "cm": 120.0}],
            "edd": [{"time": "06:00", "cm": 20.0}],
        },
    }

    forecast = build_heuristic_forecast(spot, date(2026, 6, 14), raw_data)

    assert forecast.spot == "辻堂"
    assert forecast.date == "2026-06-14"
    assert forecast.rideable is True
    assert forecast.wave_size == "腰"
    assert forecast.swell_type == "mixed"
    assert forecast.wind == "glassy"
    assert forecast.best_windows[0].start == "07:48"
    assert any(window.start == "16:56" for window in forecast.best_windows)
    assert "fish" in forecast.summary


def test_heuristic_forecast_keeps_sunset_window_when_tide_has_many_events() -> None:
    spot = get_spot("辻堂")
    raw_data = {
        "marine": {
            "summary": {"avg_wave_height_m": 0.5},
            "hours": [{"time": "17:00", "wave_height_m": 0.5, "swell_period_s": 7.0}],
        },
        "weather": {
            "sunset": "18:56",
            "hours": [{"time": "17:00", "wind_speed_mps": 1.0, "wind_direction_deg": 180.0}],
        },
        "tide": {
            "flood": [{"time": "02:54", "cm": 143.2}, {"time": "17:53", "cm": 134.1}],
            "edd": [{"time": "10:28", "cm": 2.1}, {"time": "22:23", "cm": 107.2}],
        },
    }

    forecast = build_heuristic_forecast(spot, date(2026, 6, 14), raw_data)

    assert any("サンセット" in window.reason for window in forecast.best_windows)
