from datetime import date, datetime, time

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.staff import list_staff_schedule_exceptions, revoke_staff_schedule_exception
from app.dependencies.auth import AuthenticatedActor
from app.models.attendance_event import AttendanceEvent
from app.models.employee import Employee
from app.models.employee_credential import EmployeeCredential
from app.models.staff_access import Department, DepartmentAlias, EmployeeDepartment, StaffDepartmentScope, StaffUser
from app.models.staff_schedule import StaffSemesterSchedule, StaffSemesterScheduleInterval
from app.models.staff_schedule_override import StaffScheduleBulkOperation, StaffScheduleBulkOperationChange, StaffScheduleDateOverride, StaffScheduleDateOverrideInterval
from app.models.staff_holiday_work import StaffHolidayWorkAssignment
from app.models.staff_attendance_exemption import StaffAttendanceExemption
from app.models.schedule import Schedule
from app.security import hash_password
from app.services.analytics import AnalyticsService
from tests.conftest import TestingSessionLocal


def seed_staff_mobile_data() -> None:
    session = TestingSessionLocal()
    session.query(AttendanceEvent).delete()
    session.query(Schedule).delete()
    session.query(StaffDepartmentScope).delete()
    session.query(StaffSemesterScheduleInterval).delete()
    session.query(StaffSemesterSchedule).delete()
    session.query(StaffScheduleDateOverrideInterval).delete()
    session.query(StaffScheduleDateOverride).delete()
    session.query(StaffScheduleBulkOperationChange).delete()
    session.query(StaffHolidayWorkAssignment).delete()
    session.query(StaffAttendanceExemption).delete()
    session.query(StaffUser).delete()
    session.query(EmployeeDepartment).delete()
    session.query(DepartmentAlias).delete()
    session.query(Department).delete()
    session.query(EmployeeCredential).delete()
    session.query(Employee).delete()

    department_name = "Escuela Modelo/Montejo/MTJ-Contabilidad"
    employee = Employee(
        id=1,
        nombre="Ana García",
        departamento=department_name,
        campus="Montejo",
        email="ana@example.com",
    )
    department = Department(id=3, code="mtj-contabilidad", name=department_name, campus="Montejo", active=True)
    alias = DepartmentAlias(id=1, department_id=3, alias=department_name, source="employee")
    employee_department = EmployeeDepartment(employee_id=1, department_id=3, is_primary=True)
    staff = StaffUser(
        id=10,
        email="staff@example.com",
        full_name="Staff Demo",
        password_hash=hash_password("staff2026!"),
        must_change_password=False,
        is_active=True,
        is_superadmin=False,
        employee_id=None,
    )
    scope = StaffDepartmentScope(staff_user_id=10, department_id=3)
    credentials = EmployeeCredential(employee_id=1, password_hash=hash_password("modelo2026"), must_change_password=False)
    events = [
        AttendanceEvent(
            id=1,
            employee_id=1,
            nombre="Ana García",
            departamento_raw=department_name,
            device_name="R1",
            device_serial="A-1",
            source="test",
            fecha=date(2026, 3, 27),
            tiempo=time(7, 0),
            event_ts=datetime(2026, 3, 27, 7, 0),
            created_at=datetime(2026, 3, 27, 7, 0),
        ),
        AttendanceEvent(
            id=2,
            employee_id=1,
            nombre="Ana García",
            departamento_raw=department_name,
            device_name="R1",
            device_serial="A-2",
            source="test",
            fecha=date(2026, 3, 28),
            tiempo=time(7, 5),
            event_ts=datetime(2026, 3, 28, 7, 5),
            created_at=datetime(2026, 3, 28, 7, 5),
        ),
    ]

    session.add_all([employee, department, alias, employee_department, staff, scope, credentials, *events])
    session.commit()
    session.close()


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": "staff@example.com", "password": "staff2026!"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_staff_default_week_uses_latest_attendance_event_date():
    seed_staff_mobile_data()
    client = TestClient(app)

    response = client.get("/staff/mobile/default-week", headers=auth_headers(client))

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_event_date"] == "2026-03-28"
    assert payload["start_date"] == "2026-03-23"
    assert payload["end_date"] == "2026-03-29"


def test_individual_summary_honors_requested_recent_weeks():
    seed_staff_mobile_data()
    client = TestClient(app)
    response = client.get("/staff/mobile/employee-year?department_id=3&employee_id=1&weeks=3", headers=auth_headers(client))

    assert response.status_code == 200
    assert (date.fromisoformat(response.json()["window_end"]) - date.fromisoformat(response.json()["window_start"])).days <= 20


def test_staff_can_replace_semester_schedule_for_scoped_employee():
    seed_staff_mobile_data()
    client = TestClient(app)
    headers = auth_headers(client)
    response = client.put(
        "/staff/schedules?department_id=3&employee_id=1",
        headers=headers,
        json={"academic_year": 2026, "semester": 1, "days": [
            {"weekday": 0, "intervals": [{"start": "08:00", "end": "12:00"}, {"start": "13:00", "end": "16:00"}]},
            {"weekday": 1, "intervals": []},
            {"weekday": 4, "intervals": [{"start": "08:00", "end": "16:00"}]},
        ]},
    )
    assert response.status_code == 200
    assert response.json()["is_manual"] is True
    assert len(response.json()["days"][0]["intervals"]) == 2

    response = client.get("/staff/schedules?department_id=3&employee_id=1&academic_year=2026&semester=1", headers=headers)
    assert response.status_code == 200
    assert response.json()["days"][1]["intervals"] == []

    response = client.get("/staff/schedules?department_id=3&employee_id=1&academic_year=2026&semester=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_manual"] is False
    assert response.json()["copied_from_semester"] == 1
    assert len(response.json()["days"][0]["intervals"]) == 2

    response = client.get("/staff/mobile/daily?department_id=3&start_date=2026-03-23&end_date=2026-03-29", headers=headers)
    assert response.status_code == 200
    friday = next(day for day in response.json()[0]["days"] if day["date"] == "2026-03-27")
    assert friday["scheduled_start"] == "08:00:00"


def test_staff_schedule_rejects_overlapping_intervals():
    seed_staff_mobile_data()
    client = TestClient(app)
    response = client.put(
        "/staff/schedules?department_id=3&employee_id=1",
        headers=auth_headers(client),
        json={"academic_year": 2026, "semester": 1, "days": [{"weekday": 0, "intervals": [{"start": "08:00", "end": "12:00"}, {"start": "11:00", "end": "16:00"}]}]},
    )
    assert response.status_code == 422


def test_staff_schedule_uses_legacy_schedule_as_2026_first_semester_template():
    seed_staff_mobile_data()
    session = TestingSessionLocal()
    session.add_all([
        Schedule(id=99, employee_id=1, nombre="Horario", dia_letra="Lunes", inicio=time(7), fin=time(15)),
        Schedule(id=100, employee_id=1, nombre="Horario duplicado", dia_letra="Lunes", inicio=time(7), fin=time(15)),
    ])
    session.commit()
    session.close()
    client = TestClient(app)

    response = client.get("/staff/schedules?department_id=3&employee_id=1&academic_year=2026&semester=2", headers=auth_headers(client))

    assert response.status_code == 200
    assert response.json()["is_manual"] is False
    assert response.json()["copied_from_academic_year"] == 2026
    assert response.json()["days"][0]["intervals"] == [{"start": "07:00:00", "end": "15:00:00"}]


def test_staff_bulk_schedule_preview_and_apply_uses_date_override():
    seed_staff_mobile_data()
    session = TestingSessionLocal()
    session.add(Schedule(id=99, employee_id=1, nombre="Horario", dia_letra="Lunes", inicio=time(7), fin=time(15)))
    session.commit()
    session.close()
    client = TestClient(app)
    headers = auth_headers(client)

    preview = client.post(
        "/staff/schedule-bulk/preview",
        headers=headers,
        json={"department_id": 3, "instruction": "Del 23 al 23 de marzo la entrada para todos será a las 9 am"},
    )
    assert preview.status_code == 200
    assert preview.json()["affected_employees"] == 1
    assert preview.json()["changes"][0]["new_intervals"] == [{"start": "09:00:00", "end": "15:00:00"}]

    applied = client.post("/staff/schedule-bulk/apply", headers=headers, json={"preview_token": preview.json()["preview_token"]})
    assert applied.status_code == 200
    session = TestingSessionLocal()
    audit = session.query(StaffScheduleBulkOperationChange).one()
    assert audit.previous_intervals == [{"start": "07:00:00", "end": "15:00:00"}]
    assert audit.applied_intervals == [{"start": "09:00:00", "end": "15:00:00"}]
    session.close()
    daily = client.get("/staff/mobile/daily?department_id=3&start_date=2026-03-23&end_date=2026-03-23", headers=headers)
    assert daily.status_code == 200
    assert daily.json()[0]["days"][0]["scheduled_start"] == "09:00:00"


def test_staff_bulk_schedule_requires_staff_scope():
    seed_staff_mobile_data()
    client = TestClient(app)
    response = client.post(
        "/staff/schedule-bulk/preview",
        json={"department_id": 3, "instruction": "Del 23 al 23 de marzo la entrada para todos será a las 9 am"},
    )
    assert response.status_code == 401


def test_official_holiday_is_not_counted_as_absence_without_work_assignment():
    seed_staff_mobile_data()
    session = TestingSessionLocal()
    session.add(Schedule(id=99, employee_id=1, nombre="Horario", dia_letra="Lunes", inicio=time(7), fin=time(15)))
    session.commit()
    rows = AnalyticsService(session).staff_daily_attendance(target_date=date(2026, 3, 16), department_id=3)
    assert rows[0].status == "official_holiday"
    assert rows[0].official_holiday_name == "Conmemoración del natalicio de Benito Juárez"
    session.add(StaffHolidayWorkAssignment(employee_id=1, holiday_date=date(2026, 3, 16), holiday_name="Conmemoración del natalicio de Benito Juárez", assigned_by_staff_user_id=10))
    session.commit()
    rows = AnalyticsService(session).staff_daily_attendance(target_date=date(2026, 3, 16), department_id=3)
    assert rows[0].holiday_work_authorized is True
    assert rows[0].status == "no_events"
    session.close()


def test_personal_exemption_marks_attendance_as_justified_without_touching_events():
    seed_staff_mobile_data()
    session = TestingSessionLocal()
    session.add(StaffAttendanceExemption(employee_id=1, department_id=3, target_date=date(2026, 3, 27), exempt_entry=True, exempt_exit=False, reason="permiso_staff", granted_by_staff_user_id=10))
    session.commit()
    row = AnalyticsService(session).staff_daily_attendance(target_date=date(2026, 3, 27), department_id=3)[0]
    assert row.status == "entry_excused"
    assert row.exempt_entry is True
    assert row.first_event == time(7)
    session.close()


def test_staff_schedule_exception_history_marks_current_and_preserves_replaced_change():
    seed_staff_mobile_data()
    session = TestingSessionLocal()
    first = StaffScheduleBulkOperation(staff_user_id=10, department_id=3, instruction="Entrada a las 8", operation="entry", start_date=date(2026, 8, 17), end_date=date(2026, 8, 17))
    second = StaffScheduleBulkOperation(staff_user_id=10, department_id=3, instruction="Entrada a las 9", operation="entry", start_date=date(2026, 8, 17), end_date=date(2026, 8, 17))
    session.add_all([first, second])
    session.flush()
    session.add_all([
        StaffScheduleBulkOperationChange(bulk_operation_id=first.id, employee_id=1, target_date=date(2026, 8, 17), previous_intervals=[{"start": "07:00:00", "end": "15:00:00"}], applied_intervals=[{"start": "08:00:00", "end": "15:00:00"}]),
        StaffScheduleBulkOperationChange(bulk_operation_id=second.id, employee_id=1, target_date=date(2026, 8, 17), previous_intervals=[{"start": "08:00:00", "end": "15:00:00"}], applied_intervals=[{"start": "09:00:00", "end": "15:00:00"}]),
    ])
    override = StaffScheduleDateOverride(employee_id=1, target_date=date(2026, 8, 17), bulk_operation_id=second.id)
    override.intervals = [StaffScheduleDateOverrideInterval(position=0, start=time(9), end=time(15))]
    session.add(override)
    session.commit()
    staff = session.query(StaffUser).filter(StaffUser.id == 10).one()
    actor = AuthenticatedActor(actor_type="staff", is_admin=False, must_change_password=False, staff=staff, department_ids={3})
    result = list_staff_schedule_exceptions(department_id=3, employee_id=1, actor=actor, db=session)
    assert result.total == 2
    assert sum(item.is_current for item in result.items) == 1
    assert next(item for item in result.items if item.is_current).applied_intervals[0].start == time(9)
    session.close()


def test_revoking_exception_restores_base_behavior_and_keeps_history():
    seed_staff_mobile_data()
    session = TestingSessionLocal()
    operation = StaffScheduleBulkOperation(staff_user_id=10, department_id=3, instruction="Entrada a las 9", operation="entry", start_date=date(2026, 3, 27), end_date=date(2026, 3, 27))
    session.add(operation)
    session.flush()
    session.add(StaffScheduleBulkOperationChange(bulk_operation_id=operation.id, employee_id=1, target_date=date(2026, 3, 27), previous_intervals=[{"start": "07:00:00", "end": "15:00:00"}], applied_intervals=[{"start": "09:00:00", "end": "15:00:00"}]))
    override = StaffScheduleDateOverride(employee_id=1, target_date=date(2026, 3, 27), bulk_operation_id=operation.id)
    override.intervals = [StaffScheduleDateOverrideInterval(position=0, start=time(9), end=time(15))]
    session.add(override)
    exemption = StaffAttendanceExemption(employee_id=1, department_id=3, target_date=date(2026, 3, 27), exempt_entry=True, exempt_exit=False, reason="permiso_staff", granted_by_staff_user_id=10)
    session.add(exemption)
    session.commit()
    staff = session.query(StaffUser).filter(StaffUser.id == 10).one()
    actor = AuthenticatedActor(actor_type="staff", is_admin=False, must_change_password=False, staff=staff, department_ids={3})

    revoke_staff_schedule_exception(department_id=3, employee_id=1, target_date=date(2026, 3, 27), kind="schedule_override", actor=actor, db=session)
    revoke_staff_schedule_exception(department_id=3, employee_id=1, target_date=date(2026, 3, 27), kind="attendance_exemption", actor=actor, db=session)

    assert session.query(StaffScheduleDateOverride).count() == 0
    assert session.query(StaffAttendanceExemption).one().revoked_at is not None
    assert AnalyticsService(session).staff_daily_attendance(target_date=date(2026, 3, 27), department_id=3)[0].exempt_entry is False
    result = list_staff_schedule_exceptions(department_id=3, employee_id=1, actor=actor, db=session)
    assert all(not item.is_current for item in result.items)
    assert any(item.operation == "revoke" for item in result.items)
    session.close()
