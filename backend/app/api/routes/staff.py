"""Administrative staff endpoints and mobile attendance queries."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.bootstrap import has_staff_access_schema
from app.db.session import get_db
from app.core.config import Settings, get_settings
from app.dependencies.auth import (
    AuthenticatedActor,
    get_current_actor,
    require_admin_employee,
    require_staff_actor,
    require_superadmin_actor,
)
from app.dependencies.services import get_analytics_service, get_attendance_import_service
from app.models.employee import Employee
from app.models.schedule import Schedule
from app.models.attendance_event import AttendanceEvent
from app.models.attendance_import_batch import AttendanceImportBatch
from app.models.staff_access import Department, EmployeeDepartment, StaffDepartmentScope, StaffUser
from app.models.staff_schedule import StaffSemesterSchedule, StaffSemesterScheduleInterval
from app.models.staff_schedule_override import (
    StaffScheduleBulkOperation,
    StaffScheduleBulkOperationChange,
    StaffScheduleDateOverride,
    StaffScheduleDateOverrideInterval,
)
from app.models.staff_holiday_work import StaffHolidayWorkAssignment
from app.models.staff_attendance_exemption import StaffAttendanceExemption
from app.schemas.staff import (
    AttendanceImportBatchSummary,
    AttendanceImportResult,
    DepartmentSummary,
    StaffDefaultWeek,
    StaffDepartmentEmployeeSummary,
    StaffDepartmentAssignmentRequest,
    StaffEmployeeYearSummary,
    StaffEmployeeYearWeek,
    StaffEmployeeYearWeekDay,
    StaffMobilePeriodDay,
    StaffMobilePeriodRow,
    StaffScheduleInterval,
    StaffScheduleBulkApplyRequest,
    StaffScheduleBulkApplyResult,
    StaffScheduleBulkChange,
    StaffScheduleBulkExclusion,
    StaffScheduleBulkInstructionRequest,
    StaffScheduleBulkPreview,
    StaffHolidayWorkAssignmentRequest,
    StaffHolidayWorkAssignmentResponse,
    StaffScheduleExceptionHistoryItem,
    StaffScheduleExceptionHistoryResponse,
    StaffAttendanceExemptionRequest,
    StaffAttendanceExemptionResponse,
    StaffSemesterScheduleDay,
    StaffSemesterScheduleResponse,
    StaffSemesterScheduleUpdateRequest,
    StaffUserCreateRequest,
    StaffUserSummary,
)
from app.security import create_access_token, decode_access_token, hash_password
from app.services.department_normalization import derive_department_campus
from app.services.attendance_import import AttendanceImportService
from app.services.analytics import AnalyticsService, REPORT_YEAR, REPORT_YEAR_END, REPORT_YEAR_START
from app.services.staff_schedule_bulk import BulkInstructionError, parse_bulk_instruction
from app.services.official_holidays import official_holiday_name

router = APIRouter(prefix="/staff", tags=["staff"])

_EXEMPTION_REASONS = {"incapacidad", "comision_institucional", "permiso_staff", "fuerza_mayor", "otro"}


@router.post("/attendance-exemptions", response_model=list[StaffAttendanceExemptionResponse], status_code=status.HTTP_201_CREATED)
def create_staff_attendance_exemption(
    payload: StaffAttendanceExemptionRequest,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
) -> list[StaffAttendanceExemptionResponse]:
    _require_staff_schema(db)
    _require_employee_in_department(db, payload.employee_id, payload.department_id, actor)
    reason = payload.reason.strip().lower()
    if reason not in _EXEMPTION_REASONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El motivo de exención no es válido.")
    if not payload.exempt_entry and not payload.exempt_exit:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Debes exentar entrada, salida o ambas.")
    note = (payload.note or "").strip() or None
    if reason == "otro" and note is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El motivo “Otro” requiere una nota.")
    if payload.end_date < payload.start_date or (payload.end_date - payload.start_date).days > 62:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El rango de exención debe ser válido y no exceder 63 días.")
    results = []
    for offset in range((payload.end_date - payload.start_date).days + 1):
        target_date = payload.start_date + timedelta(days=offset)
        exemption = db.query(StaffAttendanceExemption).filter(
            StaffAttendanceExemption.employee_id == payload.employee_id,
            StaffAttendanceExemption.target_date == target_date,
        ).first()
        if exemption is None:
            exemption = StaffAttendanceExemption(employee_id=payload.employee_id, department_id=payload.department_id, target_date=target_date)
            db.add(exemption)
        exemption.exempt_entry = payload.exempt_entry
        exemption.exempt_exit = payload.exempt_exit
        exemption.reason = reason
        exemption.note = note
        exemption.granted_by_staff_user_id = actor.staff.id if actor.staff else None
        exemption.revoked_at = None
        exemption.revoked_by_staff_user_id = None
        results.append(exemption)
    db.commit()
    return [_to_attendance_exemption_response(item, actor.staff.full_name if actor.staff else None) for item in results]


@router.get("/attendance-exemptions", response_model=list[StaffAttendanceExemptionResponse])
def list_staff_attendance_exemptions(
    department_id: int,
    employee_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
) -> list[StaffAttendanceExemptionResponse]:
    _require_staff_schema(db)
    _require_employee_in_department(db, employee_id, department_id, actor)
    query = db.query(StaffAttendanceExemption, StaffUser.full_name).outerjoin(StaffUser, StaffUser.id == StaffAttendanceExemption.granted_by_staff_user_id).filter(StaffAttendanceExemption.employee_id == employee_id).order_by(StaffAttendanceExemption.target_date.desc())
    if start_date:
        query = query.filter(StaffAttendanceExemption.target_date >= start_date)
    if end_date:
        query = query.filter(StaffAttendanceExemption.target_date <= end_date)
    return [_to_attendance_exemption_response(row, author) for row, author in query.all()]


@router.get("/schedule-exceptions", response_model=StaffScheduleExceptionHistoryResponse)
def list_staff_schedule_exceptions(
    department_id: int,
    employee_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    offset: int = 0,
    limit: int = 50,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
) -> StaffScheduleExceptionHistoryResponse:
    _require_staff_schema(db)
    _require_employee_in_department(db, employee_id, department_id, actor)
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El rango de fechas es inválido.")
    if offset < 0 or not 1 <= limit <= 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La paginación es inválida.")

    audit_query = (
        db.query(StaffScheduleBulkOperationChange, StaffScheduleBulkOperation, StaffUser.full_name)
        .join(StaffScheduleBulkOperation, StaffScheduleBulkOperation.id == StaffScheduleBulkOperationChange.bulk_operation_id)
        .outerjoin(StaffUser, StaffUser.id == StaffScheduleBulkOperation.staff_user_id)
        .filter(StaffScheduleBulkOperationChange.employee_id == employee_id)
    )
    overrides_query = db.query(StaffScheduleDateOverride).options(selectinload(StaffScheduleDateOverride.intervals)).filter(
        StaffScheduleDateOverride.employee_id == employee_id
    )
    if start_date:
        audit_query = audit_query.filter(StaffScheduleBulkOperationChange.target_date >= start_date)
        overrides_query = overrides_query.filter(StaffScheduleDateOverride.target_date >= start_date)
    if end_date:
        audit_query = audit_query.filter(StaffScheduleBulkOperationChange.target_date <= end_date)
        overrides_query = overrides_query.filter(StaffScheduleDateOverride.target_date <= end_date)

    overrides = overrides_query.all()
    current_by_date = {
        override.target_date: override
        for override in overrides
    }
    audit_rows = audit_query.all()
    audited_override_keys = {
        (int(change.bulk_operation_id), change.target_date)
        for change, _, _ in audit_rows
    }
    items: list[StaffScheduleExceptionHistoryItem] = []
    for change, operation, author_name in audit_rows:
        current_override = current_by_date.get(change.target_date)
        items.append(
            StaffScheduleExceptionHistoryItem(
                id=f"audit-{change.id}",
                target_date=change.target_date,
                operation=operation.operation,
                instruction=operation.instruction,
                author_name=author_name,
                created_at=operation.created_at,
                previous_intervals=[StaffScheduleInterval(**interval) for interval in change.previous_intervals],
                applied_intervals=[StaffScheduleInterval(**interval) for interval in change.applied_intervals],
                current_intervals=_to_schedule_intervals(current_override),
                is_current=current_override is not None and current_override.bulk_operation_id == operation.id,
                historical_detail_available=True,
                deletion_kind="schedule_override" if current_override is not None and current_override.bulk_operation_id == operation.id and operation.operation != "holiday_work" else None,
            )
        )
    for override in overrides:
        if override.bulk_operation_id is not None and (int(override.bulk_operation_id), override.target_date) in audited_override_keys:
            continue
        intervals = _to_schedule_intervals(override)
        items.append(
            StaffScheduleExceptionHistoryItem(
                id=f"current-{override.id}",
                target_date=override.target_date,
                operation="legacy",
                instruction="Excepción vigente sin historial de aplicación.",
                applied_intervals=intervals,
                current_intervals=intervals,
                is_current=True,
                historical_detail_available=False,
                deletion_kind="schedule_override",
            )
        )
    exemption_query = db.query(StaffAttendanceExemption, StaffUser.full_name).outerjoin(StaffUser, StaffUser.id == StaffAttendanceExemption.granted_by_staff_user_id).filter(StaffAttendanceExemption.employee_id == employee_id)
    if start_date:
        exemption_query = exemption_query.filter(StaffAttendanceExemption.target_date >= start_date)
    if end_date:
        exemption_query = exemption_query.filter(StaffAttendanceExemption.target_date <= end_date)
    for exemption, author_name in exemption_query.all():
        scope = "entrada y salida" if exemption.exempt_entry and exemption.exempt_exit else "entrada" if exemption.exempt_entry else "salida"
        revoking_staff = db.get(StaffUser, exemption.revoked_by_staff_user_id) if exemption.revoked_by_staff_user_id else None
        revoked_note = f" Revocada por {revoking_staff.full_name if revoking_staff else 'staff no identificado'} el {exemption.revoked_at.strftime('%d/%m/%Y, %H:%M')}" if exemption.revoked_at else ""
        items.append(StaffScheduleExceptionHistoryItem(id=f"attendance-exemption-{exemption.id}", target_date=exemption.target_date, operation="attendance_exemption", instruction=f"Checada exentada: {scope}. Motivo: {exemption.reason}.{f' {exemption.note}' if exemption.note else ''}{revoked_note}", author_name=author_name, created_at=exemption.created_at, applied_intervals=[], current_intervals=[], is_current=exemption.revoked_at is None, historical_detail_available=True, deletion_kind="attendance_exemption" if exemption.revoked_at is None else None))
    items.sort(key=lambda item: (item.target_date, item.created_at or datetime.min), reverse=True)
    total = len(items)
    page = items[offset:offset + limit]
    return StaffScheduleExceptionHistoryResponse(items=page, total=total, offset=offset, limit=limit, has_more=offset + limit < total)


@router.delete("/schedule-exceptions", status_code=status.HTTP_200_OK)
def revoke_staff_schedule_exception(
    department_id: int,
    employee_id: int,
    target_date: date,
    kind: str,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
) -> None:
    """Revoke a current exception while preserving its audit trail."""
    _require_staff_schema(db)
    _require_employee_in_department(db, employee_id, department_id, actor)

    if kind == "attendance_exemption":
        exemption = db.query(StaffAttendanceExemption).filter(
            StaffAttendanceExemption.employee_id == employee_id,
            StaffAttendanceExemption.target_date == target_date,
            StaffAttendanceExemption.revoked_at.is_(None),
        ).first()
        if exemption is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe una checada justificada vigente para esa fecha.")
        exemption.revoked_at = datetime.now()
        exemption.revoked_by_staff_user_id = actor.staff.id
        db.commit()
        return None

    if kind != "schedule_override":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El tipo de excepción no es válido.")
    override = db.query(StaffScheduleDateOverride).options(selectinload(StaffScheduleDateOverride.intervals)).filter(
        StaffScheduleDateOverride.employee_id == employee_id,
        StaffScheduleDateOverride.target_date == target_date,
    ).first()
    if override is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe una excepción de horario vigente para esa fecha.")
    operation = StaffScheduleBulkOperation(
        staff_user_id=actor.staff.id,
        department_id=department_id,
        instruction="Excepción de horario eliminada por staff.",
        operation="revoke",
        start_date=target_date,
        end_date=target_date,
    )
    db.add(operation)
    db.flush()
    db.add(
        StaffScheduleBulkOperationChange(
            bulk_operation_id=operation.id,
            employee_id=employee_id,
            target_date=target_date,
            previous_intervals=_serialize_interval_pairs([(item.start, item.end) for item in override.intervals]),
            applied_intervals=[],
        )
    )
    db.delete(override)
    db.commit()
    return None


@router.put("/holiday-work", response_model=StaffHolidayWorkAssignmentResponse)
def authorize_staff_holiday_work(
    payload: StaffHolidayWorkAssignmentRequest,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
) -> StaffHolidayWorkAssignmentResponse:
    _require_staff_schema(db)
    _require_employee_in_department(db, payload.employee_id, payload.department_id, actor)
    holiday_name = official_holiday_name(payload.holiday_date)
    if holiday_name is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha indicada no es un descanso oficial federal.")
    _validate_interval_pairs([(interval.start, interval.end) for interval in payload.intervals])
    assignment = db.query(StaffHolidayWorkAssignment).filter(
        StaffHolidayWorkAssignment.employee_id == payload.employee_id,
        StaffHolidayWorkAssignment.holiday_date == payload.holiday_date,
    ).first()
    if assignment is None:
        assignment = StaffHolidayWorkAssignment(
            employee_id=payload.employee_id,
            holiday_date=payload.holiday_date,
            holiday_name=holiday_name,
            assigned_by_staff_user_id=actor.staff.id if actor.staff else None,
        )
        db.add(assignment)
    else:
        assignment.holiday_name = holiday_name
        assignment.assigned_by_staff_user_id = actor.staff.id if actor.staff else None
    operation = StaffScheduleBulkOperation(
        staff_user_id=actor.staff.id if actor.staff else None,
        department_id=payload.department_id,
        instruction=f"Trabajo autorizado en descanso oficial: {holiday_name}",
        operation="holiday_work",
        start_date=payload.holiday_date,
        end_date=payload.holiday_date,
    )
    db.add(operation)
    db.flush()
    override = db.query(StaffScheduleDateOverride).options(selectinload(StaffScheduleDateOverride.intervals)).filter(
        StaffScheduleDateOverride.employee_id == payload.employee_id,
        StaffScheduleDateOverride.target_date == payload.holiday_date,
    ).first()
    previous_intervals = [] if override is None else [(item.start, item.end) for item in override.intervals]
    if override is None:
        override = StaffScheduleDateOverride(employee_id=payload.employee_id, target_date=payload.holiday_date, bulk_operation_id=operation.id)
        db.add(override)
    else:
        override.bulk_operation_id = operation.id
        override.intervals.clear()
    for position, interval in enumerate(payload.intervals):
        override.intervals.append(StaffScheduleDateOverrideInterval(position=position, start=interval.start, end=interval.end))
    db.add(
        StaffScheduleBulkOperationChange(
            bulk_operation_id=operation.id,
            employee_id=payload.employee_id,
            target_date=payload.holiday_date,
            previous_intervals=_serialize_interval_pairs(previous_intervals),
            applied_intervals=_serialize_interval_pairs([(item.start, item.end) for item in payload.intervals]),
        )
    )
    db.commit()
    return StaffHolidayWorkAssignmentResponse(employee_id=payload.employee_id, holiday_date=payload.holiday_date, holiday_name=holiday_name, intervals=payload.intervals)


@router.post("/schedule-bulk/preview", response_model=StaffScheduleBulkPreview)
def preview_staff_schedule_bulk_change(
    payload: StaffScheduleBulkInstructionRequest,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StaffScheduleBulkPreview:
    _require_staff_schema(db)
    _require_staff_department_access(actor=actor, department_id=payload.department_id)
    try:
        parsed = parse_bulk_instruction(payload.instruction)
    except BulkInstructionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    preview = _build_bulk_schedule_preview(db, payload.department_id, parsed)
    if not preview.changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No hay días con horario que puedan modificarse en el rango indicado.")
    token_payload = {
        "purpose": "staff-schedule-bulk-preview",
        "staff_user_id": actor.staff.id if actor.staff else None,
        "department_id": payload.department_id,
        "instruction": parsed.instruction,
        "operation": parsed.operation,
        "start_date": parsed.start_date.isoformat(),
        "end_date": parsed.end_date.isoformat(),
        "changes": [
            {
                "employee_id": change.employee_id,
                "target_date": change.target_date.isoformat(),
                "previous_intervals": [[item.start.isoformat(), item.end.isoformat()] for item in change.previous_intervals],
                "intervals": [[item.start.isoformat(), item.end.isoformat()] for item in change.new_intervals],
            }
            for change in preview.changes
        ],
    }
    preview.preview_token = create_access_token(token_payload, settings.auth_secret_key, expires_minutes=10)
    return preview


@router.post("/schedule-bulk/apply", response_model=StaffScheduleBulkApplyResult)
def apply_staff_schedule_bulk_change(
    payload: StaffScheduleBulkApplyRequest,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StaffScheduleBulkApplyResult:
    _require_staff_schema(db)
    token = decode_access_token(payload.preview_token, settings.auth_secret_key)
    if not token or token.get("purpose") != "staff-schedule-bulk-preview" or token.get("staff_user_id") != (actor.staff.id if actor.staff else None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La vista previa expiró o no es válida. Interpreta la instrucción nuevamente.")
    department_id = token.get("department_id")
    changes = token.get("changes")
    if not isinstance(department_id, int) or not isinstance(changes, list) or not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La vista previa no contiene cambios válidos.")
    _require_staff_department_access(actor=actor, department_id=department_id)
    employee_ids = {item.get("employee_id") for item in changes if isinstance(item, dict) and isinstance(item.get("employee_id"), int)}
    in_department = {
        int(value)
        for (value,) in db.execute(
            select(EmployeeDepartment.employee_id)
            .where(EmployeeDepartment.department_id == department_id)
            .where(EmployeeDepartment.employee_id.in_(employee_ids))
        )
    }
    if employee_ids != in_department:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Uno o más colaboradores ya no pertenecen al departamento activo. Genera una nueva vista previa.")
    operation = StaffScheduleBulkOperation(
        staff_user_id=actor.staff.id,
        department_id=department_id,
        instruction=str(token.get("instruction") or ""),
        operation=str(token.get("operation") or ""),
        start_date=date.fromisoformat(str(token.get("start_date"))),
        end_date=date.fromisoformat(str(token.get("end_date"))),
    )
    db.add(operation)
    db.flush()
    for item in changes:
        if not isinstance(item, dict):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La vista previa contiene un cambio inválido.")
        employee_id = item.get("employee_id")
        try:
            target_date = date.fromisoformat(str(item.get("target_date")))
            previous_intervals = [(time.fromisoformat(start), time.fromisoformat(end)) for start, end in item.get("previous_intervals", [])]
            intervals = [(time.fromisoformat(start), time.fromisoformat(end)) for start, end in item.get("intervals", [])]
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La vista previa contiene horarios inválidos.") from exc
        if not isinstance(employee_id, int) or not intervals:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La vista previa contiene horarios inválidos.")
        _validate_interval_pairs(intervals)
        override = db.query(StaffScheduleDateOverride).options(selectinload(StaffScheduleDateOverride.intervals)).filter(
            StaffScheduleDateOverride.employee_id == employee_id,
            StaffScheduleDateOverride.target_date == target_date,
        ).first()
        if override is None:
            override = StaffScheduleDateOverride(employee_id=employee_id, target_date=target_date, bulk_operation_id=operation.id)
            db.add(override)
        else:
            override.bulk_operation_id = operation.id
            override.intervals.clear()
        for position, (start, end) in enumerate(intervals):
            override.intervals.append(StaffScheduleDateOverrideInterval(position=position, start=start, end=end))
        db.add(
            StaffScheduleBulkOperationChange(
                bulk_operation_id=operation.id,
                employee_id=employee_id,
                target_date=target_date,
                previous_intervals=_serialize_interval_pairs(previous_intervals),
                applied_intervals=_serialize_interval_pairs(intervals),
            )
        )
    db.commit()
    return StaffScheduleBulkApplyResult(operation_id=operation.id, affected_employees=len(employee_ids), changed_days=len(changes))


@router.get("/schedules", response_model=StaffSemesterScheduleResponse)
def get_staff_semester_schedule(department_id: int, employee_id: int, academic_year: int, semester: int, actor: AuthenticatedActor = Depends(require_staff_actor), db: Session = Depends(get_db)) -> StaffSemesterScheduleResponse:
    _require_staff_schema(db)
    _validate_semester(academic_year, semester)
    _require_employee_in_department(db, employee_id, department_id, actor)
    schedule = _get_semester_schedule(db, employee_id, academic_year, semester)
    previous = None if schedule is not None else _get_previous_semester_schedule(db, employee_id, academic_year, semester)
    if schedule is None and previous is None:
        legacy_days = _legacy_schedule_days(db, employee_id)
        if legacy_days:
            return StaffSemesterScheduleResponse(
                employee_id=employee_id,
                department_id=department_id,
                academic_year=academic_year,
                semester=semester,
                is_manual=False,
                copied_from_academic_year=2026,
                copied_from_semester=1,
                days=legacy_days,
            )
    return _to_semester_schedule_response(schedule or previous, employee_id, department_id, academic_year, semester, copied_from=previous if schedule is None else None)


@router.put("/schedules", response_model=StaffSemesterScheduleResponse)
def replace_staff_semester_schedule(department_id: int, employee_id: int, payload: StaffSemesterScheduleUpdateRequest, actor: AuthenticatedActor = Depends(require_staff_actor), db: Session = Depends(get_db)) -> StaffSemesterScheduleResponse:
    _require_staff_schema(db)
    _validate_semester(payload.academic_year, payload.semester)
    _require_employee_in_department(db, employee_id, department_id, actor)
    _validate_schedule_days(payload.days)
    schedule = _get_semester_schedule(db, employee_id, payload.academic_year, payload.semester)
    if schedule is None:
        schedule = StaffSemesterSchedule(employee_id=employee_id, academic_year=payload.academic_year, semester=payload.semester, updated_by_staff_user_id=actor.staff.id if actor.staff else None)
        db.add(schedule)
        db.flush()
    else:
        schedule.updated_by_staff_user_id = actor.staff.id if actor.staff else None
        schedule.intervals.clear()
        db.flush()
    for day in payload.days:
        for interval in day.intervals:
            schedule.intervals.append(StaffSemesterScheduleInterval(weekday=day.weekday, start=interval.start, end=interval.end))
    db.commit()
    db.refresh(schedule)
    return _to_semester_schedule_response(schedule, employee_id, department_id, payload.academic_year, payload.semester)


@router.get("/mobile/default-week", response_model=StaffDefaultWeek)
def get_staff_default_week(
    _: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
) -> StaffDefaultWeek:
    _require_staff_schema(db)
    latest_event_date = db.execute(select(func.max(AttendanceEvent.fecha))).scalar_one_or_none()
    start_date, end_date = _resolve_default_attendance_week(latest_event_date)
    return StaffDefaultWeek(
        latest_event_date=latest_event_date,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/departments", response_model=list[DepartmentSummary])
def list_departments(
    actor: AuthenticatedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[DepartmentSummary]:
    _require_staff_schema(db)
    if actor.is_staff:
        query = db.query(Department).order_by(Department.name.asc())
        if not actor.is_superadmin:
            department_ids = sorted(actor.department_ids or set())
            if not department_ids:
                return []
            query = query.filter(Department.id.in_(department_ids))
        rows = query.all()
        return [_to_department_summary(row) for row in rows]
    if not actor.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso restringido al administrador")
    rows = db.query(Department).order_by(Department.name.asc()).all()
    return [_to_department_summary(row) for row in rows]


@router.get("/users", response_model=list[StaffUserSummary])
def list_staff_users(
    _: object = Depends(require_admin_employee),
    db: Session = Depends(get_db),
) -> list[StaffUserSummary]:
    _require_staff_schema(db)
    rows = (
        db.query(StaffUser)
        .options(
            selectinload(StaffUser.department_scopes).selectinload(StaffDepartmentScope.department)
        )
        .order_by(StaffUser.full_name.asc())
        .all()
    )
    return [_to_staff_user_summary(row) for row in rows]


@router.post("/users", response_model=StaffUserSummary, status_code=status.HTTP_201_CREATED)
def create_staff_user(
    payload: StaffUserCreateRequest,
    _: object = Depends(require_admin_employee),
    db: Session = Depends(get_db),
) -> StaffUserSummary:
    _require_staff_schema(db)
    normalized_email = payload.email.strip().lower()
    existing = db.query(StaffUser).filter(func.lower(StaffUser.email) == normalized_email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un staff con ese correo")
    if payload.employee_id is not None:
        employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
        if employee is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado no encontrado")
    department_ids = sorted({department_id for department_id in payload.department_ids if department_id > 0})
    departments = []
    if department_ids:
        departments = db.query(Department).filter(Department.id.in_(department_ids)).all()
        if len(departments) != len(department_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uno o más departamentos no existen")
    staff_user = StaffUser(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        must_change_password=payload.must_change_password,
        is_active=True,
        is_superadmin=payload.is_superadmin,
        employee_id=payload.employee_id,
    )
    db.add(staff_user)
    db.flush()
    for department in departments:
        db.add(StaffDepartmentScope(staff_user_id=staff_user.id, department_id=department.id))
    db.commit()
    db.refresh(staff_user)
    return _to_staff_user_summary(
        db.query(StaffUser)
        .options(selectinload(StaffUser.department_scopes).selectinload(StaffDepartmentScope.department))
        .filter(StaffUser.id == staff_user.id)
        .one()
    )


@router.put("/users/{staff_user_id}/departments", response_model=StaffUserSummary)
def replace_staff_departments(
    staff_user_id: int,
    payload: StaffDepartmentAssignmentRequest,
    _: object = Depends(require_admin_employee),
    db: Session = Depends(get_db),
) -> StaffUserSummary:
    _require_staff_schema(db)
    staff_user = (
        db.query(StaffUser)
        .options(selectinload(StaffUser.department_scopes))
        .filter(StaffUser.id == staff_user_id)
        .first()
    )
    if staff_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario staff no encontrado")
    department_ids = sorted({department_id for department_id in payload.department_ids if department_id > 0})
    if department_ids:
        departments = db.query(Department).filter(Department.id.in_(department_ids)).all()
        if len(departments) != len(department_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uno o más departamentos no existen")
    db.query(StaffDepartmentScope).filter(StaffDepartmentScope.staff_user_id == staff_user_id).delete()
    for department_id in department_ids:
        db.add(StaffDepartmentScope(staff_user_id=staff_user_id, department_id=department_id))
    db.commit()
    refreshed = (
        db.query(StaffUser)
        .options(
            selectinload(StaffUser.department_scopes).selectinload(StaffDepartmentScope.department)
        )
        .filter(StaffUser.id == staff_user_id)
        .one()
    )
    return _to_staff_user_summary(refreshed)


@router.get("/attendance-imports", response_model=list[AttendanceImportBatchSummary])
def list_attendance_imports(
    limit: int = 10,
    _: AuthenticatedActor = Depends(require_superadmin_actor),
    db: Session = Depends(get_db),
) -> list[AttendanceImportBatchSummary]:
    _require_staff_schema(db)
    safe_limit = min(max(limit, 1), 20)
    rows = (
        db.query(AttendanceImportBatch, StaffUser.full_name)
        .outerjoin(StaffUser, StaffUser.id == AttendanceImportBatch.uploaded_by_staff_user_id)
        .order_by(AttendanceImportBatch.uploaded_at.desc())
        .limit(safe_limit)
        .all()
    )
    return [_to_attendance_import_batch_summary(batch, uploader_name) for batch, uploader_name in rows]


@router.post(
    "/attendance-imports",
    response_model=AttendanceImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attendance_import(
    file: UploadFile = File(...),
    actor: AuthenticatedActor = Depends(require_superadmin_actor),
    attendance_import_service: AttendanceImportService = Depends(get_attendance_import_service),
) -> AttendanceImportResult:
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo se admiten archivos .xlsx")
    content = await file.read()
    await file.close()
    return attendance_import_service.import_workbook(content=content, filename=filename, actor=actor)


@router.get("/mobile/daily", response_model=list[StaffMobilePeriodRow])
def get_staff_daily_attendance(
    department_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    analytics: AnalyticsService = Depends(get_analytics_service),
    db: Session = Depends(get_db),
) -> list[StaffMobilePeriodRow]:
    _require_staff_schema(db)
    if department_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="department_id inválido")
    if not actor.can_access_department(department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este departamento")
    resolved_start_date, resolved_end_date = _resolve_week_period(start_date=start_date, end_date=end_date)
    period_rows = analytics.staff_period_attendance(
        period_start=resolved_start_date,
        period_end=resolved_end_date,
        department_id=department_id,
    )
    return [
        StaffMobilePeriodRow(
            employee_id=row.employee_id,
            employee_name=row.employee_name,
            employee_email=row.employee_email,
            department_id=row.department_id,
            department_name=row.department_name,
            campus=row.campus,
            total_events=row.total_events,
            active_days=row.active_days,
            period_start=row.period_start,
            period_end=row.period_end,
            days=[
                StaffMobilePeriodDay(
                    date=day.date,
                    first_event=day.first_event,
                    last_event=day.last_event,
                    entry_event=day.entry_event,
                    exit_event=day.exit_event,
                    entry_event_inferred=day.entry_event_inferred,
                    exit_event_inferred=day.exit_event_inferred,
                    total_events=day.total_events,
                    scheduled_start=day.scheduled_start,
                    scheduled_end=day.scheduled_end,
                    schedule_intervals=[
                        StaffScheduleInterval(start=interval.start, end=interval.end)
                        for interval in day.schedule_intervals
                    ],
                    has_mixed_schedule=day.has_mixed_schedule,
                    is_official_holiday=day.is_official_holiday,
                    official_holiday_name=day.official_holiday_name,
                    holiday_work_authorized=day.holiday_work_authorized,
                    exempt_entry=day.exempt_entry,
                    exempt_exit=day.exempt_exit,
                    exemption_reason=day.exemption_reason,
                    status=day.status,
                )
                for day in row.days
            ],
        )
        for row in period_rows
    ]


@router.get("/mobile/employees", response_model=list[StaffDepartmentEmployeeSummary])
def list_staff_department_employees(
    department_id: int,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    db: Session = Depends(get_db),
) -> list[StaffDepartmentEmployeeSummary]:
    _require_staff_schema(db)
    _require_staff_department_access(actor=actor, department_id=department_id)
    rows = db.execute(
        select(
            Employee.id.label("employee_id"),
            Employee.nombre.label("employee_name"),
            Employee.email.label("employee_email"),
            Employee.campus.label("campus"),
            Employee.departamento.label("legacy_department"),
        )
        .join(EmployeeDepartment, EmployeeDepartment.employee_id == Employee.id)
        .where(EmployeeDepartment.department_id == department_id)
        .order_by(Employee.nombre.asc())
    ).all()
    return [
        StaffDepartmentEmployeeSummary(
            id=int(row.employee_id),
            name=row.employee_name,
            email=row.employee_email,
            campus=row.campus or _campus_from_employee_department(row.legacy_department),
        )
        for row in rows
    ]


@router.get("/mobile/employee-year", response_model=StaffEmployeeYearSummary)
def get_staff_employee_year_summary(
    department_id: int,
    employee_id: int,
    weeks: int = 4,
    actor: AuthenticatedActor = Depends(require_staff_actor),
    analytics: AnalyticsService = Depends(get_analytics_service),
    db: Session = Depends(get_db),
) -> StaffEmployeeYearSummary:
    _require_staff_schema(db)
    _require_staff_department_access(actor=actor, department_id=department_id)
    if employee_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="employee_id inválido")
    if not 1 <= weeks <= 52:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="weeks debe estar entre 1 y 52")

    employee_row = db.execute(
        select(
            Employee.id.label("employee_id"),
            Employee.nombre.label("employee_name"),
            Employee.email.label("employee_email"),
            Employee.campus.label("campus"),
            Employee.departamento.label("legacy_department"),
            Department.id.label("department_id"),
            Department.name.label("department_name"),
        )
        .join(EmployeeDepartment, EmployeeDepartment.employee_id == Employee.id)
        .join(Department, Department.id == EmployeeDepartment.department_id)
        .where(EmployeeDepartment.department_id == department_id)
        .where(Employee.id == employee_id)
    ).first()
    if employee_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Colaborador no encontrado en este departamento")

    report_window_end = min(_resolve_previous_week_sunday(date.today()), REPORT_YEAR_END)
    if report_window_end < REPORT_YEAR_START:
        report_window_end = REPORT_YEAR_START
    window_start = max(REPORT_YEAR_START, report_window_end - timedelta(days=weeks * 7 - 1))
    annual_rows = analytics.staff_period_attendance(
        period_start=window_start,
        period_end=report_window_end,
        department_id=department_id,
        employee_ids=[employee_id],
    )
    if not annual_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Colaborador no encontrado")
    annual_row = annual_rows[0]
    registered_schedule_intervals = _resolve_registered_schedule_intervals(annual_row.days)

    return StaffEmployeeYearSummary(
        employee_id=int(employee_row.employee_id),
        employee_name=employee_row.employee_name,
        employee_email=employee_row.employee_email,
        campus=employee_row.campus or _campus_from_employee_department(employee_row.legacy_department),
        department_id=int(employee_row.department_id),
        department_name=employee_row.department_name,
        report_year=REPORT_YEAR,
        window_start=window_start,
        window_end=report_window_end,
        total_days=annual_row.active_days,
        late_days=sum(1 for day in annual_row.days if day.status == "late"),
        justified_days=sum(1 for day in annual_row.days if day.status in {"justified", "entry_excused", "exit_excused"}),
        punctuality_rate=(
            (
                annual_row.active_days
                - sum(1 for day in annual_row.days if day.status in {"late", "absence"})
            )
            / annual_row.active_days
            if annual_row.active_days
            else 1.0
        ),
        registered_schedule_intervals=[
            StaffScheduleInterval(start=interval.start, end=interval.end)
            for interval in registered_schedule_intervals
        ],
        weeks=_group_year_days_by_week(days=annual_row.days, report_window_end=report_window_end),
    )


def _to_department_summary(row: Department) -> DepartmentSummary:
    return DepartmentSummary(
        id=row.id,
        code=row.code,
        name=row.name,
        campus=row.campus,
        active=row.active,
    )


def _to_staff_user_summary(row: StaffUser) -> StaffUserSummary:
    ordered_departments = sorted(
        (scope.department for scope in row.department_scopes if scope.department is not None),
        key=lambda department: department.name,
    )
    return StaffUserSummary(
        id=row.id,
        email=row.email,
        full_name=row.full_name,
        employee_id=row.employee_id,
        is_active=row.is_active,
        is_superadmin=row.is_superadmin,
        must_change_password=row.must_change_password,
        departments=[_to_department_summary(department) for department in ordered_departments],
    )


def _to_attendance_import_batch_summary(
    batch: AttendanceImportBatch,
    uploaded_by: str | None,
) -> AttendanceImportBatchSummary:
    return AttendanceImportBatchSummary(
        id=batch.id,
        original_filename=batch.original_filename,
        uploaded_at=batch.uploaded_at,
        uploaded_by=uploaded_by,
        total_rows=batch.total_rows,
        imported_rows=batch.imported_rows,
        skipped_duplicates=batch.skipped_duplicates,
        invalid_rows=batch.invalid_rows,
        duplicate_breakdown=batch.duplicate_breakdown or [],
        auto_created_employees=batch.auto_created_employees or [],
    )


def _require_staff_schema(db: Session) -> None:
    if not has_staff_access_schema(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Las tablas de staff/departamentos no están instaladas en PostgreSQL. Aplica la migración y solicita privilegios de CREATE en schema public.",
        )


def _require_staff_department_access(*, actor: AuthenticatedActor, department_id: int) -> None:
    if department_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="department_id inválido")
    if not actor.can_access_department(department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este departamento")


def _validate_semester(academic_year: int, semester: int) -> None:
    if not 2000 <= academic_year <= 2100 or semester not in {1, 2}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Periodo semestral inválido")


def _require_employee_in_department(db: Session, employee_id: int, department_id: int, actor: AuthenticatedActor) -> None:
    _require_staff_department_access(actor=actor, department_id=department_id)
    if employee_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="employee_id inválido")
    exists = db.execute(select(EmployeeDepartment.employee_id).where(EmployeeDepartment.employee_id == employee_id).where(EmployeeDepartment.department_id == department_id)).first()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Colaborador no encontrado en este departamento")


def _get_semester_schedule(db: Session, employee_id: int, academic_year: int, semester: int) -> StaffSemesterSchedule | None:
    return db.query(StaffSemesterSchedule).options(selectinload(StaffSemesterSchedule.intervals)).filter(
        StaffSemesterSchedule.employee_id == employee_id,
        StaffSemesterSchedule.academic_year == academic_year,
        StaffSemesterSchedule.semester == semester,
    ).first()


def _get_previous_semester_schedule(db: Session, employee_id: int, academic_year: int, semester: int) -> StaffSemesterSchedule | None:
    return db.query(StaffSemesterSchedule).options(selectinload(StaffSemesterSchedule.intervals)).filter(
        StaffSemesterSchedule.employee_id == employee_id,
        (StaffSemesterSchedule.academic_year < academic_year) | ((StaffSemesterSchedule.academic_year == academic_year) & (StaffSemesterSchedule.semester < semester)),
    ).order_by(StaffSemesterSchedule.academic_year.desc(), StaffSemesterSchedule.semester.desc()).first()


def _legacy_schedule_days(db: Session, employee_id: int) -> list[StaffSemesterScheduleDay]:
    weekday_by_name = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4, "Sábado": 5, "Domingo": 6}
    grouped: dict[int, set[tuple[object, object]]] = {}
    for day_name, start, end in db.execute(select(Schedule.dia_letra, Schedule.inicio, Schedule.fin).where(Schedule.employee_id == employee_id)):
        weekday = weekday_by_name.get(day_name or "")
        if weekday is not None:
            grouped.setdefault(weekday, set()).add((start, end))
    return [StaffSemesterScheduleDay(weekday=weekday, intervals=[StaffScheduleInterval(start=start, end=end) for start, end in sorted(grouped.get(weekday, set()))]) for weekday in range(7)] if grouped else []


def _to_semester_schedule_response(schedule, employee_id: int, department_id: int, academic_year: int, semester: int, copied_from=None) -> StaffSemesterScheduleResponse:
    grouped: dict[int, set[tuple[object, object]]] = {}
    if schedule is not None:
        for interval in schedule.intervals:
            grouped.setdefault(interval.weekday, set()).add((interval.start, interval.end))
    return StaffSemesterScheduleResponse(employee_id=employee_id, department_id=department_id, academic_year=academic_year, semester=semester, is_manual=schedule is not None and copied_from is None, copied_from_academic_year=copied_from.academic_year if copied_from is not None else None, copied_from_semester=copied_from.semester if copied_from is not None else None, days=[StaffSemesterScheduleDay(weekday=weekday, intervals=[StaffScheduleInterval(start=start, end=end) for start, end in sorted(grouped.get(weekday, set()))]) for weekday in range(7)])


def _validate_schedule_days(days: list[StaffSemesterScheduleDay]) -> None:
    seen_days: set[int] = set()
    for day in days:
        if day.weekday in seen_days:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cada día solo puede enviarse una vez")
        seen_days.add(day.weekday)
        previous_end = None
        for interval in sorted(day.intervals, key=lambda value: value.start):
            if interval.start >= interval.end:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La hora de inicio debe ser anterior a la hora de fin")
            if previous_end is not None and interval.start < previous_end:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Los bloques de un día no pueden traslaparse")
            previous_end = interval.end


def _validate_interval_pairs(intervals: list[tuple[time, time]]) -> None:
    previous_end = None
    for start, end in sorted(intervals):
        if start >= end:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El cambio produce un bloque de horario inválido.")
        if previous_end is not None and start < previous_end:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El cambio produce bloques de horario traslapados.")
        previous_end = end


def _serialize_interval_pairs(intervals: list[tuple[time, time]]) -> list[dict[str, str]]:
    return [{"start": start.isoformat(), "end": end.isoformat()} for start, end in intervals]


def _to_schedule_intervals(override: StaffScheduleDateOverride | None) -> list[StaffScheduleInterval]:
    if override is None:
        return []
    return [StaffScheduleInterval(start=interval.start, end=interval.end) for interval in override.intervals]


def _to_attendance_exemption_response(exemption: StaffAttendanceExemption, author_name: str | None) -> StaffAttendanceExemptionResponse:
    return StaffAttendanceExemptionResponse(
        id=exemption.id,
        target_date=exemption.target_date,
        exempt_entry=exemption.exempt_entry,
        exempt_exit=exemption.exempt_exit,
        reason=exemption.reason,
        note=exemption.note,
        author_name=author_name,
        created_at=exemption.created_at,
        revoked_at=exemption.revoked_at,
    )


def _build_bulk_schedule_preview(db: Session, department_id: int, parsed) -> StaffScheduleBulkPreview:
    employees = db.execute(
        select(Employee.id, Employee.nombre)
        .join(EmployeeDepartment, EmployeeDepartment.employee_id == Employee.id)
        .where(EmployeeDepartment.department_id == department_id)
        .order_by(Employee.nombre.asc())
    ).all()
    employee_ids = [int(row.id) for row in employees]
    analytics = AnalyticsService(db)
    dates = [parsed.start_date + timedelta(days=offset) for offset in range((parsed.end_date - parsed.start_date).days + 1)]
    schedule_maps = {
        current_date: analytics._resolved_schedule_interval_map(employee_ids, current_date)
        for current_date in dates
    }
    changes: list[StaffScheduleBulkChange] = []
    exclusions: list[StaffScheduleBulkExclusion] = []
    affected_ids: set[int] = set()
    for employee in employees:
        employee_id = int(employee.id)
        for current_date in dates:
            previous = schedule_maps[current_date].get((employee_id, current_date.weekday()), [])
            if not previous:
                exclusions.append(StaffScheduleBulkExclusion(employee_id=employee_id, employee_name=employee.nombre, target_date=current_date, reason="Sin horario registrado; no se creó un turno nuevo."))
                continue
            pairs = [(interval.start, interval.end) for interval in previous]
            if parsed.operation == "entry":
                pairs[0] = (parsed.start, pairs[0][1])
            elif parsed.operation == "exit":
                pairs[-1] = (pairs[-1][0], parsed.end)
            else:
                pairs = [(parsed.start, parsed.end)]
            try:
                _validate_interval_pairs(pairs)
            except HTTPException as exc:
                exclusions.append(StaffScheduleBulkExclusion(employee_id=employee_id, employee_name=employee.nombre, target_date=current_date, reason=exc.detail))
                continue
            new_intervals = [StaffScheduleInterval(start=start, end=end) for start, end in pairs]
            if [(item.start, item.end) for item in previous] == pairs:
                continue
            changes.append(StaffScheduleBulkChange(employee_id=employee_id, employee_name=employee.nombre, target_date=current_date, previous_intervals=[StaffScheduleInterval(start=item.start, end=item.end) for item in previous], new_intervals=new_intervals))
            affected_ids.add(employee_id)
    return StaffScheduleBulkPreview(
        department_id=department_id,
        instruction=parsed.instruction,
        operation=parsed.operation,
        start_date=parsed.start_date,
        end_date=parsed.end_date,
        affected_employees=len(affected_ids),
        changes=changes,
        exclusions=exclusions,
        preview_token="",
    )


def _resolve_week_period(*, start_date: date | None, end_date: date | None) -> tuple[date, date]:
    if start_date is None and end_date is None:
        today = date.today()
        current_week_monday = today - timedelta(days=today.weekday())
        start_date = current_week_monday - timedelta(days=7)
        end_date = start_date + timedelta(days=6)
        return start_date, end_date
    if start_date is None or end_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes enviar start_date y end_date para el periodo completo")
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El periodo es inválido")
    if start_date.weekday() != 0 or end_date.weekday() != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El periodo debe iniciar en lunes y terminar en domingo",
        )
    if (end_date - start_date).days > 27:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El periodo máximo permitido es de 4 semanas",
        )
    return start_date, end_date


def _resolve_default_attendance_week(latest_event_date: date | None) -> tuple[date, date]:
    if latest_event_date is not None:
        start_date = latest_event_date - timedelta(days=latest_event_date.weekday())
        end_date = start_date + timedelta(days=6)
        return start_date, end_date
    return _resolve_week_period(start_date=None, end_date=None)


def _resolve_previous_week_sunday(today: date) -> date:
    current_week_monday = today - timedelta(days=today.weekday())
    return current_week_monday - timedelta(days=1)


def _campus_from_employee_department(department_name: str | None) -> str | None:
    return derive_department_campus(department_name)


def _resolve_registered_schedule_intervals(days):
    for day in days:
        if day.schedule_intervals:
            return day.schedule_intervals
    return []


def _group_year_days_by_week(*, days, report_window_end: date) -> list[StaffEmployeeYearWeek]:
    weeks: list[StaffEmployeeYearWeek] = []
    current_week_start: date | None = None
    current_week_days: list[StaffEmployeeYearWeekDay] = []

    def flush_week() -> None:
        nonlocal current_week_start, current_week_days
        if current_week_start is None or not current_week_days:
            return
        computed_week_end = min(current_week_start + timedelta(days=6), report_window_end)
        active_days = sum(1 for day in current_week_days if day.total_events > 0)
        total_events = sum(day.total_events for day in current_week_days)
        weeks.append(
            StaffEmployeeYearWeek(
                week_start=max(current_week_start, REPORT_YEAR_START),
                week_end=computed_week_end,
                active_days=active_days,
                total_events=total_events,
                days=current_week_days,
                entry_event_inferred=day.entry_event_inferred,
                exit_event_inferred=day.exit_event_inferred,
            )
        )
        current_week_start = None
        current_week_days = []

    for day in days:
        week_start = day.date - timedelta(days=day.date.weekday())
        if current_week_start != week_start:
            flush_week()
            current_week_start = week_start
        current_week_days.append(
            StaffEmployeeYearWeekDay(
                date=day.date,
                first_event=day.first_event,
                last_event=day.last_event,
                entry_event=day.entry_event,
                exit_event=day.exit_event,
                entry_event_inferred=day.entry_event_inferred,
                exit_event_inferred=day.exit_event_inferred,
                total_events=day.total_events,
                scheduled_start=day.scheduled_start,
                scheduled_end=day.scheduled_end,
                schedule_intervals=[
                    StaffScheduleInterval(start=interval.start, end=interval.end)
                    for interval in day.schedule_intervals
                ],
                has_mixed_schedule=day.has_mixed_schedule,
                is_official_holiday=day.is_official_holiday,
                official_holiday_name=day.official_holiday_name,
                holiday_work_authorized=day.holiday_work_authorized,
                exempt_entry=day.exempt_entry,
                exempt_exit=day.exempt_exit,
                exemption_reason=day.exemption_reason,
                status=day.status,
            )
        )
    flush_week()
    weeks.reverse()
    return weeks
