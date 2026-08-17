"""Pydantic schemas for analytics endpoints."""
from datetime import date, time

from pydantic import BaseModel


class GlobalMetrics(BaseModel):
    window_start: date
    window_end: date
    total_events: int
    on_time_events: int
    late_events: int
    punctuality_rate: float
    active_employees: int


class CampusMetrics(BaseModel):
    campus: str
    total_events: int
    active_employees: int
    on_time_events: int
    late_events: int
    punctuality_rate: float


class WeeklyCheckinDay(BaseModel):
    weekday: int
    entrada: time | None
    is_late: bool | None
    expected: time | None
    inferred: bool = False


class EmployeeWeeklyCheckin(BaseModel):
    week_start: date
    week_end: date
    days: list[WeeklyCheckinDay]


class EmployeeRanking(BaseModel):
    id: int
    nombre: str
    departamento: str
    campus: str
    total_days: int
    late_days: int
    punctuality_rate: float
    entrada: time | None = None
    weekly_checkins: list[EmployeeWeeklyCheckin] | None = None


class TimelineEntry(BaseModel):
    title: str
    detail: str
    time: str


class DashboardResponse(BaseModel):
    global_metrics: GlobalMetrics
    campus_metrics: list[CampusMetrics]
    top_employees: list[EmployeeRanking]
    timeline: list[TimelineEntry]


class WeeklyCampusPosition(BaseModel):
    campus: str
    position: int
    position_delta: int
    total_events: int
    on_time_events: int
    late_events: int
    punctuality_rate: float


class WeeklyHistoryRow(BaseModel):
    week_start: date
    week_end: date
    campuses: list[WeeklyCampusPosition]
