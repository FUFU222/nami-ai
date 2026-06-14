from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from nami_ai.agent.forecaster import forecast_from_query
from nami_ai.domain.schema import SurfForecast

app = FastAPI(title="nami-ai", version="0.1.0")


class ForecastRequest(BaseModel):
    query: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/forecast", response_model=SurfForecast)
async def forecast_get(query: str) -> SurfForecast:
    return await forecast_from_query(query)


@app.post("/forecast", response_model=SurfForecast)
async def forecast_post(request: ForecastRequest) -> SurfForecast:
    return await forecast_from_query(request.query)
