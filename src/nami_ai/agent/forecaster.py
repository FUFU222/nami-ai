from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI

from nami_ai.config.spots import SurfSpot, resolve_spot
from nami_ai.domain.knowledge import (
    RIDER_PROFILE,
    body_size_from_wave_height,
    classify_swell,
    classify_wind,
    parse_target_date,
    recommend_sunset_window,
    tide_movement_windows,
)
from nami_ai.domain.schema import SurfForecast, TimeWindow
from nami_ai.tools.marine import fetch_marine_forecast
from nami_ai.tools.tide import fetch_tide
from nami_ai.tools.weather import fetch_weather_forecast


async def forecast_from_query(query: str, *, use_llm: bool = True) -> SurfForecast:
    load_dotenv()
    spot = resolve_spot(query)
    target_date = parse_target_date(query)
    api_key = os.getenv("GOOGLE_API_KEY")

    if use_llm and api_key:
        try:
            raw_data = await collect_raw_data_with_agent(spot, target_date, api_key=api_key)
            return await judge_with_gemini(spot, target_date, raw_data, api_key=api_key)
        except Exception as exc:
            raw_data = await collect_raw_data(spot, target_date)
            forecast = build_heuristic_forecast(spot, target_date, raw_data)
            forecast.caution = _append_caution(
                forecast.caution,
                f"Gemini 判断に失敗したためローカル判定で返しています: {exc}",
            )
            return forecast

    raw_data = await collect_raw_data(spot, target_date)
    return build_heuristic_forecast(spot, target_date, raw_data)


async def collect_raw_data(spot: SurfSpot, target_date: date) -> dict[str, Any]:
    marine, weather, tide = await asyncio.gather(
        fetch_marine_forecast(spot, target_date),
        fetch_weather_forecast(spot, target_date),
        fetch_tide(target_date),
    )
    return {"marine": marine, "weather": weather, "tide": tide}


async def collect_raw_data_with_agent(
    spot: SurfSpot, target_date: date, *, api_key: str
) -> dict[str, Any]:
    collected: dict[str, Any] = {}

    async def marine_tool() -> str:
        """Fetch wave and swell forecast for the selected Shonan surf spot."""
        data = await fetch_marine_forecast(spot, target_date)
        collected["marine"] = data
        return json.dumps(data, ensure_ascii=False)

    async def weather_tool() -> str:
        """Fetch wind, temperature, sunrise, and sunset forecast."""
        data = await fetch_weather_forecast(spot, target_date)
        collected["weather"] = data
        return json.dumps(data, ensure_ascii=False)

    async def tide_tool() -> str:
        """Fetch Enoshima tide forecast for the target date."""
        data = await fetch_tide(target_date)
        collected["tide"] = data
        return json.dumps(data, ensure_ascii=False)

    tools = [
        StructuredTool.from_function(
            coroutine=marine_tool,
            name="marine_forecast",
            description="Get Open-Meteo Marine wave and swell data.",
        ),
        StructuredTool.from_function(
            coroutine=weather_tool,
            name="weather_forecast",
            description="Get Open-Meteo Weather wind, temperature, sunrise, and sunset data.",
        ),
        StructuredTool.from_function(
            coroutine=tide_tool,
            name="tide_forecast",
            description="Get tide736 Enoshima tide data.",
        ),
    ]

    llm = _make_llm(api_key=api_key, temperature=0.0)
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "あなたはサーフ予報のデータ収集エージェントです。"
            "判断はせず、marine_forecast、weather_forecast、tide_forecast の3つを必ず1回ずつ呼んでください。"
            "最後に取得完了だけを短く返してください。"
        ),
    )
    await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"{target_date.isoformat()} の {spot.name} の波、風、潮を集めてください。",
                }
            ]
        }
    )

    missing = {"marine", "weather", "tide"} - collected.keys()
    if missing:
        direct = await collect_raw_data(spot, target_date)
        collected.update({name: direct[name] for name in missing})
    return collected


async def judge_with_gemini(
    spot: SurfSpot, target_date: date, raw_data: dict[str, Any], *, api_key: str
) -> SurfForecast:
    llm = _make_llm(api_key=api_key, temperature=0.2)
    structured = llm.with_structured_output(SurfForecast, method="json_schema")
    prompt = _judgement_prompt(spot, target_date, raw_data)
    result = await structured.ainvoke(
        [
            (
                "system",
                "あなたは湘南のサーフコンディションを論理的に判定するAIです。"
                "必ずサーファー目線の日本語で、指定されたPydanticスキーマだけを返してください。",
            ),
            ("human", prompt),
        ]
    )
    if isinstance(result, SurfForecast):
        return result
    return SurfForecast.model_validate(result)


def build_heuristic_forecast(
    spot: SurfSpot, target_date: date, raw_data: dict[str, Any]
) -> SurfForecast:
    marine = raw_data["marine"]
    weather = raw_data["weather"]
    tide = raw_data["tide"]

    sunset = weather.get("sunset") or "18:00"
    preferred_time = _preferred_session_time(sunset)
    marine_hour = _nearest_hour(marine.get("hours", []), preferred_time)
    weather_hour = _nearest_hour(weather.get("hours", []), preferred_time)

    wave_height = float(marine_hour.get("wave_height_m") or marine["summary"].get("avg_wave_height_m") or 0.0)
    swell_period = float(marine_hour.get("swell_period_s") or marine_hour.get("wave_period_s") or 0.0)
    swell_type = classify_swell(swell_period)
    wave_size = body_size_from_wave_height(wave_height)

    wind_speed = float(weather_hour.get("wind_speed_mps") or 0.0)
    wind_direction = float(weather_hour.get("wind_direction_deg") or spot.offshore_dir)
    wind = classify_wind(spot, wind_direction_deg=wind_direction, wind_speed_mps=wind_speed)

    tide_windows = tide_movement_windows(tide)
    sunset_window = recommend_sunset_window(sunset) if sunset else None
    best_windows = _select_best_windows(tide_windows, sunset_window)

    rideable = _is_rideable_for_profile(
        wave_height=wave_height,
        wave_size=wave_size,
        wind=wind,
        wind_speed=wind_speed,
    )
    score = _score_conditions(
        wave_height=wave_height,
        swell_period=swell_period,
        swell_direction=marine_hour.get("swell_direction_deg"),
        spot=spot,
        wind=wind,
    )
    if not rideable:
        score = min(score, 3)
    score_reasons = _score_reasons(
        wave_height=wave_height,
        wave_size=wave_size,
        swell_period=swell_period,
        swell_direction=marine_hour.get("swell_direction_deg"),
        spot=spot,
        wind=wind,
        wind_speed=wind_speed,
    )
    caution = _caution(wave_size=wave_size, wave_height=wave_height, wind=wind, wind_speed=wind_speed, rideable=rideable)

    return SurfForecast(
        spot=spot.name,
        date=target_date.isoformat(),
        score=score,
        rideable=rideable,
        wave_size=wave_size,
        wave_height_m=round(wave_height, 2),
        swell_period_s=round(swell_period, 1),
        swell_type=swell_type,
        wind=wind,
        best_windows=best_windows,
        summary=_summary(
            wave_size=wave_size,
            wave_height=wave_height,
            swell_type=swell_type,
            wind=wind,
            tide_name=tide.get("tide_name"),
            rideable=rideable,
            score_reasons=score_reasons,
        ),
        caution=caution,
    )


def _make_llm(*, api_key: str, temperature: float) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        api_key=api_key,
        temperature=temperature,
    )


def _judgement_prompt(spot: SurfSpot, target_date: date, raw_data: dict[str, Any]) -> str:
    return (
        "次の生データとサーフ知識に基づいて SurfForecast を作成してください。\n"
        f"対象: {spot.name} / {target_date.isoformat()}\n"
        f"ライダー: {json.dumps(RIDER_PROFILE, ensure_ascii=False)}\n"
        "知識:\n"
        "- 湘南の遠浅ビーチブレイクでは沖波高の約0.6〜0.7掛けを体感フェイスとして見る。\n"
        "- 8秒以上はground、6秒以下はwind、それ以外はmixed。\n"
        "- 風速2m/s未満はglassy。オフショア、クロス、オンショアをスポットのoffshore_dirから判断。\n"
        "- 満潮・干潮間の3〜7分、サンセット1.5〜2時間前を優先。\n"
        "- 6'0 fish, 32Lなので腰から遊べるが、頭オーバーは苦手。\n"
        f"spot metadata: {json.dumps(spot.__dict__, ensure_ascii=False)}\n"
        f"raw data: {json.dumps(raw_data, ensure_ascii=False)}"
    )


def _nearest_hour(hours: list[dict[str, Any]], preferred_hhmm: str) -> dict[str, Any]:
    if not hours:
        return {}
    preferred = _time_to_minutes(preferred_hhmm)
    return min(hours, key=lambda hour: abs(_time_to_minutes(hour["time"]) - preferred))


def _preferred_session_time(sunset: str) -> str:
    minutes = _time_to_minutes(sunset[:5]) - 105
    return _minutes_to_time(minutes)


def _score_conditions(
    *,
    wave_height: float,
    swell_period: float,
    swell_direction: Any,
    spot: SurfSpot,
    wind: str,
) -> int:
    score = 1
    if wave_height >= 0.4:
        score += 1
    if wave_height >= 0.7:
        score += 1
    if swell_period >= 7.0:
        score += 1
    if wind in {"offshore", "glassy"}:
        score += 1
    elif wind == "onshore":
        score -= 1
    if swell_direction is not None and _direction_in_window(float(swell_direction), spot.swell_window):
        score += 1
    return max(1, min(5, score))


def _is_rideable_for_profile(
    *, wave_height: float, wave_size: str, wind: str, wind_speed: float
) -> bool:
    if wave_size == "overhead" or wave_height >= 1.5:
        return False
    if wave_height < 0.4:
        return False
    if wind == "onshore" and wind_speed >= 4.0:
        return False
    return True


def _score_reasons(
    *,
    wave_height: float,
    wave_size: str,
    swell_period: float,
    swell_direction: Any,
    spot: SurfSpot,
    wind: str,
    wind_speed: float,
) -> list[str]:
    reasons = [f"沖波高{wave_height:.2f}mで体感{wave_size}"]
    if swell_period >= 7.0:
        reasons.append(f"周期{swell_period:.1f}秒で少し押しがある")
    else:
        reasons.append(f"周期{swell_period:.1f}秒でパワーは控えめ")

    if wind == "glassy":
        reasons.append(f"風{wind_speed:.1f}m/sで面は期待できる")
    elif wind == "offshore":
        reasons.append(f"風{wind_speed:.1f}m/sのオフショア")
    elif wind == "onshore":
        reasons.append(f"風{wind_speed:.1f}m/sのオンショア")
    else:
        reasons.append(f"風{wind_speed:.1f}m/sのクロス")

    if swell_direction is not None:
        if _direction_in_window(float(swell_direction), spot.swell_window):
            reasons.append("うねり方向がポイントに合う")
        else:
            reasons.append("うねり方向はポイントから少し外れる")
    return reasons


def _direction_in_window(direction: float, window: tuple[float, float]) -> bool:
    start, end = window
    if start <= end:
        return start <= direction <= end
    return direction >= start or direction <= end


def _summary(
    *,
    wave_size: str,
    wave_height: float,
    swell_type: str,
    wind: str,
    tide_name: str | None,
    rideable: bool,
    score_reasons: list[str],
) -> str:
    board = RIDER_PROFILE["board"]
    reason_text = "判断理由: " + "、".join(score_reasons) + "。"
    if not rideable:
        if wave_size == "overhead" or wave_height >= 1.5:
            return f"{wave_size}前後で{board}には強め。無理しない判断が必要。{reason_text}"
        return f"{wave_size}前後で物足りない。{board} でも入る価値は薄め。{reason_text}"

    wind_text = {
        "glassy": "風は弱く面は期待できる",
        "offshore": "オフショアで面は整いやすい",
        "cross": "クロス気味で少しヨレそう",
        "onshore": "オンショアでまとまりに欠ける",
    }.get(wind, wind)
    tide_text = f"{tide_name}で潮の動きも見たい" if tide_name else "潮の動きも見たい"
    return f"{wave_size}前後、沖波高{wave_height:.2f}mの{swell_type}寄り。{board} なら遊べる。{wind_text}ので、{tide_text}。{reason_text}"


def _caution(*, wave_size: str, wave_height: float, wind: str, wind_speed: float, rideable: bool) -> str | None:
    cautions: list[str] = []
    if not rideable:
        cautions.append("サイズ不足または風の影響で満足度は低めです")
    if wind == "onshore":
        cautions.append(f"オンショア {wind_speed:.1f}m/s で面が乱れやすいです")
    if wave_size == "overhead" or wave_height >= 1.5:
        cautions.append("頭オーバー以上はライダープロファイル的に無理しない判断が必要です")
    return " / ".join(cautions) if cautions else None


def _dedupe_windows(windows: list[TimeWindow]) -> list[TimeWindow]:
    seen: set[tuple[str, str]] = set()
    deduped: list[TimeWindow] = []
    for window in windows:
        key = (window.start, window.end)
        if key not in seen:
            seen.add(key)
            deduped.append(window)
    return deduped


def _select_best_windows(
    tide_windows: list[TimeWindow], sunset_window: TimeWindow | None
) -> list[TimeWindow]:
    daytime_tides = [
        window
        for window in tide_windows
        if 5 * 60 <= _time_to_minutes(window.start) <= 18 * 60
    ]
    combined = _dedupe_windows(daytime_tides + ([sunset_window] if sunset_window else []))
    if len(combined) <= 3:
        return combined
    if sunset_window and all(window.reason != sunset_window.reason for window in combined[:3]):
        return combined[:2] + [sunset_window]
    return combined[:3]


def _append_caution(existing: str | None, addition: str) -> str:
    return f"{existing} / {addition}" if existing else addition


def _time_to_minutes(hhmm: str) -> int:
    hour, minute = hhmm[:5].split(":")
    return int(hour) * 60 + int(minute)


def _minutes_to_time(minutes: int) -> str:
    minutes %= 24 * 60
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}"
