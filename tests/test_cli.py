from nami_ai.cli import format_forecast
from nami_ai.domain.schema import SurfForecast, TimeWindow


def test_format_forecast_outputs_human_readable_text() -> None:
    forecast = SurfForecast(
        spot="辻堂",
        date="2026-06-14",
        score=4,
        rideable=True,
        wave_size="腰",
        wave_height_m=0.62,
        swell_period_s=7.5,
        swell_type="mixed",
        wind="glassy",
        best_windows=[TimeWindow(start="16:56", end="17:26", reason="サンセット前")],
        summary="fish なら十分遊べる。",
        caution=None,
    )

    output = format_forecast(forecast)

    assert "辻堂 / 2026-06-14" in output
    assert "スコア: 4/5" in output
    assert "入る価値: あり" in output
    assert "16:56-17:26" in output
    assert "fish なら十分遊べる。" in output
