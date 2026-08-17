"""Employee lookup endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import AuthenticatedEmployee, get_current_employee, require_admin_employee
from app.models.employee import Employee
from app.schemas.auth import (
    AttendanceRecordEvent,
    AttendanceRecordSummary,
    AuthEmployee,
    SelfAttendanceRecordResponse,
)
from app.schemas.analytics import EmployeeWeeklyCheckin, WeeklyCheckinDay
from app.schemas.employee import EmployeeSummary
from app.services.analytics import AnalyticsService
from app.dependencies.services import get_analytics_service

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/", response_model=list[EmployeeSummary])
def list_employees(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin_employee),
) -> list[EmployeeSummary]:
    employees = db.query(Employee).order_by(Employee.nombre.asc()).limit(50).all()
    return [
        EmployeeSummary(id=e.id, nombre=e.nombre, departamento=e.departamento, email=e.email)
        for e in employees
    ]


@router.get("/me/attendance", response_model=SelfAttendanceRecordResponse)
def get_my_attendance_record(
    authenticated: AuthenticatedEmployee = Depends(get_current_employee),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> SelfAttendanceRecordResponse:
    employee = authenticated.employee
    record = analytics.employee_attendance_record(employee.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado no encontrado")
    return SelfAttendanceRecordResponse(
        employee=AuthEmployee(
            id=employee.id,
            nombre=employee.nombre,
            email=employee.email,
            departamento=employee.departamento,
            campus=employee.campus,
            must_change_password=authenticated.must_change_password,
            is_admin=authenticated.is_admin,
        ),
        summary=AttendanceRecordSummary(
            total_days=record.employee.total_days,
            late_days=record.employee.late_days,
            punctuality_rate=record.employee.punctuality_rate,
            expected_entry_time=record.employee.entrada,
        ),
        weekly_checkins=_map_weekly_checkins(record.employee.weekly_checkins),
        recent_events=[
            AttendanceRecordEvent(
                id=event.id,
                fecha=event.fecha,
                tiempo=event.tiempo,
                event_ts=event.event_ts,
                device_name=event.device_name,
                device_serial=event.device_serial,
                source=event.source,
            )
            for event in record.recent_events
        ],
    )


def _map_weekly_checkins(weekly_rows):
    if not weekly_rows:
        return []
    mapped: list[EmployeeWeeklyCheckin] = []
    for week in weekly_rows:
        days = getattr(week, "days", []) or []
        mapped.append(
            EmployeeWeeklyCheckin(
                week_start=week.week_start,
                week_end=week.week_end,
                days=[
                    WeeklyCheckinDay(
                        weekday=day.weekday,
                        entrada=day.entrada,
                        is_late=day.is_late,
                        expected=getattr(day, "expected", None),
                        inferred=getattr(day, "inferred", False),
                    )
                    for day in days
                ],
            )
        )
    return mapped
