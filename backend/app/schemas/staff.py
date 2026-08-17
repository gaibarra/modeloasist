"""Schemas for staff management and mobile attendance queries."""
from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field


class DepartmentSummary(BaseModel):
    id: int
    code: str
    name: str
    campus: str | None = None
    active: bool


class StaffUserSummary(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    employee_id: int | None = None
    is_active: bool
    is_superadmin: bool
    must_change_password: bool
    departments: list[DepartmentSummary]


class StaffUserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    employee_id: int | None = None
    department_ids: list[int] = []
    is_superadmin: bool = False
    must_change_password: bool = True


class StaffDepartmentAssignmentRequest(BaseModel):
    department_ids: list[int] = []


class StaffScheduleInterval(BaseModel):
    start: time
    end: time


class StaffSemesterScheduleDay(BaseModel):
    weekday: int = Field(ge=0, le=6)
    intervals: list[StaffScheduleInterval] = []


class StaffSemesterScheduleResponse(BaseModel):
    employee_id: int
    department_id: int
    academic_year: int
    semester: int
    is_manual: bool
    copied_from_academic_year: int | None = None
    copied_from_semester: int | None = None
    days: list[StaffSemesterScheduleDay]


class StaffSemesterScheduleUpdateRequest(BaseModel):
    academic_year: int = Field(ge=2000, le=2100)
    semester: int = Field(ge=1, le=2)
    days: list[StaffSemesterScheduleDay]


class StaffMobilePeriodDay(BaseModel):
    date: date
    first_event: time | None = None
    last_event: time | None = None
    entry_event: time | None = None
    exit_event: time | None = None
    entry_event_inferred: bool = False
    exit_event_inferred: bool = False
    total_events: int
    scheduled_start: time | None = None
    scheduled_end: time | None = None
    schedule_intervals: list[StaffScheduleInterval] = []
    has_mixed_schedule: bool = False
    status: str


class StaffMobilePeriodRow(BaseModel):
    employee_id: int
    employee_name: str
    employee_email: str | None = None
    department_id: int
    department_name: str
    campus: str | None = None
    total_events: int
    active_days: int
    period_start: date
    period_end: date
    days: list[StaffMobilePeriodDay]


class StaffDefaultWeek(BaseModel):
    latest_event_date: date | None = None
    start_date: date
    end_date: date


class StaffDepartmentEmployeeSummary(BaseModel):
    id: int
    name: str
    email: str | None = None
    campus: str | None = None


class StaffEmployeeYearWeekDay(BaseModel):
    date: date
    first_event: time | None = None
    last_event: time | None = None
    entry_event: time | None = None
    exit_event: time | None = None
    entry_event_inferred: bool = False
    exit_event_inferred: bool = False
    total_events: int
    scheduled_start: time | None = None
    scheduled_end: time | None = None
    schedule_intervals: list[StaffScheduleInterval] = []
    has_mixed_schedule: bool = False
    status: str


class StaffEmployeeYearWeek(BaseModel):
    week_start: date
    week_end: date
    active_days: int
    total_events: int
    days: list[StaffEmployeeYearWeekDay]


class StaffEmployeeYearSummary(BaseModel):
    employee_id: int
    employee_name: str
    employee_email: str | None = None
    campus: str | None = None
    department_id: int
    department_name: str
    report_year: int
    window_start: date
    window_end: date
    total_days: int
    late_days: int
    punctuality_rate: float
    registered_schedule_intervals: list[StaffScheduleInterval] = []
    weeks: list[StaffEmployeeYearWeek]


class AttendanceImportAutoCreatedEmployee(BaseModel):
    employee_id: int
    nombre: str
    departamento: str
    email: str
    lookup_reason: str
    lookup_label: str


class AttendanceImportDuplicateReason(BaseModel):
    reason: str
    label: str
    count: int


class AttendanceImportRowError(BaseModel):
    row_number: int
    message: str


class AttendanceImportBatchSummary(BaseModel):
    id: str
    original_filename: str
    uploaded_at: datetime
    uploaded_by: str | None = None
    total_rows: int
    imported_rows: int
    skipped_duplicates: int
    invalid_rows: int
    duplicate_breakdown: list[AttendanceImportDuplicateReason] = []
    auto_created_employees: list[AttendanceImportAutoCreatedEmployee] = []


class AttendanceImportResult(BaseModel):
    batch: AttendanceImportBatchSummary
    row_errors: list[AttendanceImportRowError] = []
