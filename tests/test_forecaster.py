import asyncio
from datetime import date

from nami_ai.agent import forecaster
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


def test_heuristic_forecast_allows_weak_onshore_for_fish_board() -> None:
    spot = get_spot("辻堂")
    raw_data = _raw_data_for_rideable_tsujido()
    raw_data["weather"]["hours"][0]["wind_speed_mps"] = 2.5
    raw_data["weather"]["hours"][0]["wind_direction_deg"] = 205.0

    forecast = build_heuristic_forecast(spot, date(2026, 6, 14), raw_data)

    assert forecast.wind == "onshore"
    assert forecast.rideable is True
    assert forecast.caution is not None
    assert "オンショア" in forecast.caution


def test_heuristic_forecast_marks_overhead_as_not_rideable_for_rider_profile() -> None:
    spot = get_spot("辻堂")
    raw_data = _raw_data_for_rideable_tsujido()
    raw_data["marine"]["hours"][0]["wave_height_m"] = 1.7
    raw_data["marine"]["hours"][0]["swell_period_s"] = 9.0
    raw_data["weather"]["hours"][0]["wind_speed_mps"] = 1.0
    raw_data["weather"]["hours"][0]["wind_direction_deg"] = 20.0

    forecast = build_heuristic_forecast(spot, date(2026, 6, 14), raw_data)

    assert forecast.wave_size == "overhead"
    assert forecast.rideable is False
    assert forecast.score <= 3
    assert forecast.caution is not None
    assert "頭オーバー" in forecast.caution


def test_forecast_from_query_falls_back_when_gemini_path_fails(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy")

    async def failing_collect_raw_data_with_agent(*args, **kwargs):
        raise RuntimeError("gemini tool path failed")

    async def fake_collect_raw_data(*args, **kwargs):
        return _raw_data_for_rideable_tsujido()

    monkeypatch.setattr(
        forecaster,
        "collect_raw_data_with_agent",
        failing_collect_raw_data_with_agent,
    )
    monkeypatch.setattr(forecaster, "collect_raw_data", fake_collect_raw_data)

    forecast = asyncio.run(forecaster.forecast_from_query("明日の辻堂どう？"))

    assert forecast.spot == "辻堂"
    assert forecast.rideable is True
    assert forecast.caution is not None
    assert "Gemini 判断に失敗" in forecast.caution


def _raw_data_for_rideable_tsujido() -> dict:
    return {
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
