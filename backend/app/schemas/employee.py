"""Pydantic schemas for employee-facing endpoints."""
from datetime import datetime, time
from pydantic import BaseModel, EmailStr


class EmployeeBase(BaseModel):
    nombre: str
    departamento: str
    email: EmailStr


class EmployeeSummary(EmployeeBase):
    id: int


class AttendanceEventSummary(BaseModel):
    id: int
    fecha: datetime
    device_name: str | None = None
    device_serial: str | None = None
    event_ts: datetime


class ScheduleWindow(BaseModel):
    dia_letra: str | None = None
    inicio: time
    fin: time
    mat_nombre: str | None = None
    gpo_clave: str | None = None


class EmployeeInsight(BaseModel):
    employee: EmployeeSummary
    punctuality_score: float
    attendance_rate: float
    ai_feedback: str
    recent_events: list[AttendanceEventSummary]
    schedule_windows: list[ScheduleWindow]
