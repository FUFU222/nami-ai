from nami_ai import cli
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
        reasons=["沖波高0.62mで体感腰", "風1.5m/sで面は期待できる"],
        summary="fish なら十分遊べる。",
        caution=None,
    )

    output = format_forecast(forecast)

    assert "辻堂 / 2026-06-14" in output
    assert "スコア: 4/5" in output
    assert "入る価値: あり" in output
    assert "16:56-17:26" in output
    assert "判断理由:" in output
    assert "- 沖波高0.62mで体感腰" in output
    assert "fish なら十分遊べる。" in output


def test_cli_main_prints_forecast_from_query(monkeypatch, capsys) -> None:
    async def fake_forecast_from_query(query: str) -> SurfForecast:
        assert query == "明後日の 鵠沼どう？"
        return _sample_forecast()

    monkeypatch.setattr(cli, "forecast_from_query", fake_forecast_from_query)

    exit_code = cli.main(["明後日の", "鵠沼どう？"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "辻堂 / 2026-06-14" in captured.out
    assert "判断理由:" in captured.out


def test_cli_main_returns_1_when_forecast_fails(monkeypatch, capsys) -> None:
    async def failing_forecast_from_query(query: str) -> SurfForecast:
        raise ValueError("ポイント名を解釈できませんでした")

    monkeypatch.setattr(cli, "forecast_from_query", failing_forecast_from_query)

    exit_code = cli.main(["明日のハワイどう？"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "nami-ai error" in captured.err
    assert "ポイント名" in captured.err


def _sample_forecast() -> SurfForecast:
    return SurfForecast(
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
        reasons=["沖波高0.62mで体感腰", "風1.5m/sで面は期待できる"],
        summary="fish なら十分遊べる。",
        caution=None,
    )
