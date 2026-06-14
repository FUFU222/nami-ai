from __future__ import annotations

import argparse
import asyncio
import sys

from nami_ai.agent.forecaster import forecast_from_query
from nami_ai.domain.schema import SurfForecast


def format_forecast(forecast: SurfForecast) -> str:
    rideable = "あり" if forecast.rideable else "なし"
    windows = "\n".join(
        f"- {window.start}-{window.end}: {window.reason}" for window in forecast.best_windows
    )
    lines = [
        f"{forecast.spot} / {forecast.date}",
        f"スコア: {forecast.score}/5",
        f"入る価値: {rideable}",
        (
            "波: "
            f"{forecast.wave_size} "
            f"({forecast.wave_height_m:.2f}m, {forecast.swell_period_s:.1f}s, {forecast.swell_type})"
        ),
        f"風: {forecast.wind}",
        "おすすめ時間:",
        windows or "- 目立った推奨時間なし",
        f"一言: {forecast.summary}",
    ]
    if forecast.caution:
        lines.append(f"注意: {forecast.caution}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="湘南サーフコンディション判定 CLI")
    parser.add_argument("query", nargs="+", help='例: "明日の鵠沼どう？"')
    args = parser.parse_args(argv)
    query = " ".join(args.query)

    try:
        forecast = asyncio.run(forecast_from_query(query))
    except Exception as exc:
        print(f"nami-ai error: {exc}", file=sys.stderr)
        return 1

    print(format_forecast(forecast))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
