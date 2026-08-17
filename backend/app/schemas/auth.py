"""Schemas for authentication and self-service attendance."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.analytics import EmployeeWeeklyCheckin


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class AuthEmployee(BaseModel):
    id: int
    nombre: str
    email: EmailStr
    departamento: str
    campus: str | None = None
    must_change_password: bool
    is_admin: bool


class AuthStaff(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    employee_id: int | None = None
    must_change_password: bool
    is_superadmin: bool
    department_ids: list[int] = []


class AuthSubject(BaseModel):
    actor_type: Literal["employee", "staff"]
    employee: AuthEmployee | None = None
    staff: AuthStaff | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    actor_type: Literal["employee", "staff"]
    employee: AuthEmployee | None = None
    staff: AuthStaff | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)


class AttendanceRecordEvent(BaseModel):
    id: int
    fecha: date
    tiempo: time
    event_ts: datetime
    device_name: str | None = None
    device_serial: str | None = None
    source: str | None = None


class AttendanceRecordSummary(BaseModel):
    total_days: int
    late_days: int
    punctuality_rate: float
    expected_entry_time: time | None = None


class SelfAttendanceRecordResponse(BaseModel):
    employee: AuthEmployee
    summary: AttendanceRecordSummary
    weekly_checkins: list[EmployeeWeeklyCheckin]
    recent_events: list[AttendanceRecordEvent]