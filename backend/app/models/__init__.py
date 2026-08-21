"""Expose ORM models for Alembic autogenerate."""
from app.models.attendance_event import AttendanceEvent
from app.models.attendance_import_batch import AttendanceImportBatch
from app.models.attendance_weekly_metric import AttendanceWeeklyMetric
from app.models.employee import Employee
from app.models.inferred_schedule import InferredSchedule
from app.models.schedule import Schedule
from app.models.staff_access import Department, DepartmentAlias, EmployeeDepartment, StaffDepartmentScope, StaffUser
from app.models.staff_schedule import StaffSemesterSchedule, StaffSemesterScheduleInterval
from app.models.staff_schedule_override import (
	StaffScheduleBulkOperation,
	StaffScheduleBulkOperationChange,
	StaffScheduleDateOverride,
	StaffScheduleDateOverrideInterval,
)
from app.models.staff_holiday_work import StaffHolidayWorkAssignment
from app.models.staff_attendance_exemption import StaffAttendanceExemption

__all__ = [
	"AttendanceEvent",
	"AttendanceImportBatch",
	"AttendanceWeeklyMetric",
	"Department",
	"DepartmentAlias",
	"Employee",
	"EmployeeDepartment",
	"InferredSchedule",
	"Schedule",
	"StaffDepartmentScope",
	"StaffSemesterSchedule",
	"StaffSemesterScheduleInterval",
	"StaffScheduleBulkOperation",
	"StaffScheduleBulkOperationChange",
	"StaffScheduleDateOverride",
	"StaffScheduleDateOverrideInterval",
	"StaffHolidayWorkAssignment",
	"StaffAttendanceExemption",
	"StaffUser",
]
