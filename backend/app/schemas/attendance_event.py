"""Attendance event schemas."""
from datetime import date, datetime, time
from pydantic import BaseModel


class AttendanceEventBase(BaseModel):
    employee_id: int
    nombre: str
    departamento_raw: str | None = None
    device_name: str | None = None
    device_serial: str | None = None
    source: str | None = None
    fecha: date
    tiempo: time
    event_ts: datetime


class AttendanceEventRead(AttendanceEventBase):
    id: int

    class Config:
        from_attributes = True
