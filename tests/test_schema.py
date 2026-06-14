from nami_ai.domain.schema import SurfForecast, TimeWindow


def test_surf_forecast_schema_accepts_required_output_shape() -> None:
    forecast = SurfForecast(
        spot="辻堂",
        date="2026-06-14",
        score=3,
        rideable=True,
        wave_size="腰",
        wave_height_m=0.6,
        swell_period_s=7.5,
        swell_type="mixed",
        wind="offshore",
        best_windows=[TimeWindow(start="16:30", end="17:30", reason="サンセット前")],
        summary="小波だけど fish なら遊べる。",
        caution=None,
    )

    assert forecast.model_dump()["best_windows"][0]["start"] == "16:30"
