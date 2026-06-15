from fastapi.testclient import TestClient

from nami_ai.api import main as api_main
from nami_ai.api.main import app
from nami_ai.domain.schema import SurfForecast, TimeWindow


def test_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_forecast_returns_400_for_unrecognized_spot() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/forecast", params={"query": "明日のハワイどう？"})

    assert response.status_code == 400
    assert "ポイント名" in response.json()["detail"]


def test_forecast_get_returns_structured_forecast(monkeypatch) -> None:
    async def fake_forecast_from_query(query: str) -> SurfForecast:
        assert query == "明日の辻堂どう？"
        return _sample_forecast()

    monkeypatch.setattr(api_main, "forecast_from_query", fake_forecast_from_query)
    client = TestClient(app)

    response = client.get("/forecast", params={"query": "明日の辻堂どう？"})

    assert response.status_code == 200
    assert response.json()["spot"] == "辻堂"
    assert response.json()["best_windows"][0]["start"] == "16:56"


def test_forecast_post_returns_structured_forecast(monkeypatch) -> None:
    async def fake_forecast_from_query(query: str) -> SurfForecast:
        assert query == "明日の辻堂どう？"
        return _sample_forecast()

    monkeypatch.setattr(api_main, "forecast_from_query", fake_forecast_from_query)
    client = TestClient(app)

    response = client.post("/forecast", json={"query": "明日の辻堂どう？"})

    assert response.status_code == 200
    assert response.json()["spot"] == "辻堂"
    assert response.json()["rideable"] is True


def _sample_forecast() -> SurfForecast:
    return SurfForecast(
        spot="辻堂",
        date="2026-06-15",
        score=3,
        rideable=True,
        wave_size="腰",
        wave_height_m=0.6,
        swell_period_s=7.5,
        swell_type="mixed",
        wind="glassy",
        best_windows=[TimeWindow(start="16:56", end="17:26", reason="サンセット前")],
        summary="fish なら十分遊べる。",
        caution=None,
    )
