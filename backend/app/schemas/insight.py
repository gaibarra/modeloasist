"""Schemas describing AI-generated insights."""
from datetime import date
from pydantic import BaseModel


class BehaviorTrend(BaseModel):
    label: str
    value: float
    delta: float


class InsightPayload(BaseModel):
    employee_id: int
    period_start: date
    period_end: date
    punctuality_rank: int | None = None
    punctuality_percentile: float | None = None
    recommendations: list[str]
    behavior_trends: list[BehaviorTrend]
