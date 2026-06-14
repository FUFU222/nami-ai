from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    start: str
    end: str
    reason: str


class SurfForecast(BaseModel):
    spot: str
    date: str
    score: int = Field(ge=1, le=5)
    rideable: bool
    wave_size: str
    wave_height_m: float
    swell_period_s: float
    swell_type: Literal["ground", "wind", "mixed"]
    wind: str
    best_windows: list[TimeWindow]
    summary: str
    caution: str | None = None
