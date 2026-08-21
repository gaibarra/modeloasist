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


class StaffScheduleBulkInstructionRequest(BaseModel):
    department_id: int = Field(gt=0)
    instruction: str = Field(min_length=8, max_length=1000)


class StaffScheduleBulkApplyRequest(BaseModel):
    preview_token: str = Field(min_length=20, max_length=20000)


class StaffScheduleBulkChange(BaseModel):
    employee_id: int
    employee_name: str
    target_date: date
    previous_intervals: list[StaffScheduleInterval]
    new_intervals: list[StaffScheduleInterval]


class StaffScheduleBulkExclusion(BaseModel):
    employee_id: int
    employee_name: str
    target_date: date
    reason: str


class StaffScheduleBulkPreview(BaseModel):
    department_id: int
    instruction: str
    operation: str
    start_date: date
    end_date: date
    affected_employees: int
    changes: list[StaffScheduleBulkChange]
    exclusions: list[StaffScheduleBulkExclusion]
    preview_token: str


class StaffScheduleBulkApplyResult(BaseModel):
    operation_id: int
    affected_employees: int
    changed_days: int


class StaffHolidayWorkAssignmentRequest(BaseModel):
    department_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)
    holiday_date: date
    intervals: list[StaffScheduleInterval] = [StaffScheduleInterval(start=time(7), end=time(15))]


class StaffHolidayWorkAssignmentResponse(BaseModel):
    employee_id: int
    holiday_date: date
    holiday_name: str
    intervals: list[StaffScheduleInterval]


class StaffAttendanceExemptionRequest(BaseModel):
    department_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)
    start_date: date
    end_date: date
    exempt_entry: bool = False
    exempt_exit: bool = False
    reason: str = Field(min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class StaffAttendanceExemptionResponse(BaseModel):
    id: int
    target_date: date
    exempt_entry: bool
    exempt_exit: bool
    reason: str
    note: str | None = None
    author_name: str | None = None
    created_at: datetime | None = None
    revoked_at: datetime | None = None


class StaffScheduleExceptionHistoryItem(BaseModel):
    id: str
    target_date: date
    operation: str
    instruction: str | None = None
    author_name: str | None = None
    created_at: datetime | None = None
    previous_intervals: list[StaffScheduleInterval] = []
    applied_intervals: list[StaffScheduleInterval]
    current_intervals: list[StaffScheduleInterval]
    is_current: bool
    historical_detail_available: bool
    deletion_kind: str | None = None


class StaffScheduleExceptionHistoryResponse(BaseModel):
    items: list[StaffScheduleExceptionHistoryItem]
    total: int
    offset: int
    limit: int
    has_more: bool


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
    is_official_holiday: bool = False
    official_holiday_name: str | None = None
    holiday_work_authorized: bool = False
    exempt_entry: bool = False
    exempt_exit: bool = False
    exemption_reason: str | None = None
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
    is_official_holiday: bool = False
    official_holiday_name: str | None = None
    holiday_work_authorized: bool = False
    exempt_entry: bool = False
    exempt_exit: bool = False
    exemption_reason: str | None = None
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
    justified_days: int = 0
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
