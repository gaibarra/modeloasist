from datetime import date, datetime, time, timedelta

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models.attendance_event import AttendanceEvent
from app.models.attendance_weekly_metric import AttendanceWeeklyMetric
from app.models.employee_credential import EmployeeCredential
from app.models.employee import Employee
from app.models.inferred_schedule import InferredSchedule
from app.models.schedule import Schedule
from app.models.staff_access import Department, DepartmentAlias, EmployeeDepartment, StaffDepartmentScope, StaffUser
from app.security import hash_password
from tests.conftest import TestingSessionLocal


DAY_LABELS = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def seed_data() -> None:
    session = TestingSessionLocal()
    session.query(AttendanceEvent).delete()
    session.query(StaffDepartmentScope).delete()
    session.query(StaffUser).delete()
    session.query(EmployeeDepartment).delete()
    session.query(DepartmentAlias).delete()
    session.query(Department).delete()
    session.query(InferredSchedule).delete()
    session.query(AttendanceWeeklyMetric).delete()
    session.query(Schedule).delete()
    session.query(EmployeeCredential).delete()
    session.query(Employee).delete()

    today = date.today()
    merida_employee = Employee(
        id=1,
        nombre="Ana García",
        departamento="Escuela Modelo/Mérida/CME-Ingeniería",
        campus="Mérida",
        email="ana@example.com",
    )
    montejo_employee = Employee(
        id=2,
        nombre="Luis Pérez",
        departamento="Escuela Modelo/Montejo/MTJ-Primaria",
        campus="Montejo",
        email="luis@example.com",
    )
    admin_employee = Employee(
        id=3,
        nombre="Gerardo Aibarra",
        departamento="Escuela Modelo/Mérida/Rectoría",
        campus="Mérida",
        email="gaibarra@hotmail.com",
    )
    credentials = [
        EmployeeCredential(employee_id=1, password_hash=hash_password("modelo2026"), must_change_password=False),
        EmployeeCredential(employee_id=2, password_hash=hash_password("modelo2026"), must_change_password=False),
        EmployeeCredential(employee_id=3, password_hash=hash_password("modelo2026"), must_change_password=False),
    ]
    departments = [
        Department(id=1, code="merida-ingenieria", name=merida_employee.departamento, campus="Mérida", active=True),
        Department(id=2, code="montejo-primaria", name=montejo_employee.departamento, campus="Montejo", active=True),
        Department(id=3, code="merida-rectoria", name=admin_employee.departamento, campus="Mérida", active=True),
    ]
    aliases = [
        DepartmentAlias(id=1, department_id=1, alias=merida_employee.departamento, source="employee"),
        DepartmentAlias(id=2, department_id=2, alias=montejo_employee.departamento, source="employee"),
        DepartmentAlias(id=3, department_id=3, alias=admin_employee.departamento, source="employee"),
    ]
    employee_departments = [
        EmployeeDepartment(employee_id=1, department_id=1, is_primary=True),
        EmployeeDepartment(employee_id=2, department_id=2, is_primary=True),
        EmployeeDepartment(employee_id=3, department_id=3, is_primary=True),
    ]

    schedules = [
        Schedule(
            id=1,
            employee_id=1,
            nombre="Entrada",
            esc_clave="CME",
            prog_clave="CME",
            dia_letra=DAY_LABELS[today.weekday()],
            inicio=time(7, 0),
            fin=time(9, 0),
        )
    ]

    events = []
    for offset in range(3):
        event_date = today - timedelta(days=offset)
        events.append(
            AttendanceEvent(
                id=offset * 2 + 1,
                employee_id=1,
                nombre="Ana García",
                departamento_raw="Escuela Modelo/Mérida/CME-Ingeniería",
                device_name="R1",
                device_serial=f"A-{offset}",
                source="test",
                fecha=event_date,
                tiempo=time(6, 55),
                event_ts=datetime.combine(event_date, time(6, 55)),
                created_at=datetime.combine(event_date, time(6, 55)),
            )
        )
        montejo_time = time(7, 45) if offset == 0 else time(7, 20)
        events.append(
            AttendanceEvent(
                id=offset * 2 + 2,
                employee_id=2,
                nombre="Luis Pérez",
                departamento_raw="Escuela Modelo/Montejo/MTJ-Primaria",
                device_name="R2",
                device_serial=f"B-{offset}",
                source="test",
                fecha=event_date,
                tiempo=montejo_time,
                event_ts=datetime.combine(event_date, montejo_time),
                created_at=datetime.combine(event_date, montejo_time),
            )
        )

    session.add_all([
        merida_employee,
        montejo_employee,
        admin_employee,
        *credentials,
        *departments,
        *aliases,
        *employee_departments,
        *schedules,
        *events,
    ])
    session.commit()
    session.close()


def login_as_admin(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": "gaibarra@hotmail.com", "password": "modelo2026"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_endpoint_returns_real_metrics():
    seed_data()
    client = TestClient(app)
    headers = login_as_admin(client)

    response = client.get("/analytics/dashboard", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["global_metrics"]["total_events"] == 6
    assert len(payload["campus_metrics"]) == 4
    assert payload["top_employees"], "Expected employee ranking data"
    assert payload["timeline"], "Timeline should not be empty"


def test_weekly_history_endpoint_returns_rows():
    seed_data()
    client = TestClient(app)
    headers = login_as_admin(client)

    response = client.get("/analytics/weekly-history?weeks=2", headers=headers)

    assert response.status_code == 200
    rows = response.json()
    assert rows, "Expected at least one weekly row"
    first_row = rows[0]
    assert "week_start" in first_row
    assert len(first_row["campuses"]) == 4


def test_employee_rankings_endpoint_supports_filters():
    seed_data()
    client = TestClient(app)
    headers = login_as_admin(client)

    response = client.get(
        "/analytics/employee-rankings",
        params={"campus": "Mérida", "search": "Ana", "limit": 10},
        headers=headers,
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["nombre"] == "Ana García"
    assert rows[0]["campus"] == "Mérida"


def test_employee_rankings_ignore_events_from_2025():
    seed_data()
    session = TestingSessionLocal()
    session.add(
        AttendanceEvent(
            id=999,
            employee_id=1,
            nombre="Ana García",
            departamento_raw="Escuela Modelo/Mérida/CME-Ingeniería",
            device_name="R1",
            device_serial="A-999",
            source="test",
            fecha=date(2025, 12, 31),
            tiempo=time(6, 50),
            event_ts=datetime(2025, 12, 31, 6, 50),
            created_at=datetime(2025, 12, 31, 6, 50),
        )
    )
    session.commit()
    session.close()

    client = TestClient(app)
    headers = login_as_admin(client)

    response = client.get(
        "/analytics/employee-rankings",
        params={"search": "Ana", "limit": 10},
        headers=headers,
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["total_days"] == 3


def test_employee_rankings_can_limit_weekly_payload_to_specific_employee_ids():
    seed_data()
    client = TestClient(app)
    headers = login_as_admin(client)

    response = client.get(
        "/analytics/employee-rankings",
        params={"employeeIds": "1", "includeWeekly": True, "weeklyWeeks": 12, "limit": 0},
        headers=headers,
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["weekly_checkins"]


def test_analytics_requires_admin_access():
    seed_data()
    client = TestClient(app)

    response = client.get("/analytics/dashboard")

    assert response.status_code == 401


def test_staff_mobile_daily_requires_scope_and_returns_schedule_status():
    seed_data()
    session = TestingSessionLocal()
    staff = StaffUser(
        id=20,
        email="scope.staff@example.com",
        full_name="Scoped Staff",
        password_hash=hash_password("staff2026!"),
        must_change_password=False,
        is_active=True,
        is_superadmin=False,
    )
    session.add(staff)
    session.flush()
    session.add(StaffDepartmentScope(staff_user_id=20, department_id=1))
    session.commit()
    session.close()

    client = TestClient(app)
    login_response = client.post(
        "/auth/login",
        json={"email": "scope.staff@example.com", "password": "staff2026!"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = client.get(
        "/staff/mobile/daily",
        params={"department_id": 1, "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=6 - date.today().weekday()))},
        headers={"Authorization": f"Bearer {token}"},
    )

    if date.today().weekday() != 0:
        monday = date.today() - timedelta(days=date.today().weekday())
        sunday = monday + timedelta(days=6)
        response = client.get(
            "/staff/mobile/daily",
            params={"department_id": 1, "start_date": str(monday), "end_date": str(sunday)},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["employee_name"] == "Ana García"
    assert rows[0]["period_start"]
    assert rows[0]["period_end"]
    assert len(rows[0]["days"]) == 7
    assert any(day["total_events"] >= 0 for day in rows[0]["days"])
    scheduled_days = [day for day in rows[0]["days"] if day["schedule_intervals"]]
    assert scheduled_days
    assert scheduled_days[0]["has_mixed_schedule"] is False
    assert scheduled_days[0]["entry_event"] == scheduled_days[0]["first_event"]
    assert scheduled_days[0]["entry_event_inferred"] is True


def test_staff_mobile_daily_rejects_unauthorized_department_scope():
    seed_data()
    session = TestingSessionLocal()
    staff = StaffUser(
        id=21,
        email="scope.blocked@example.com",
        full_name="Blocked Staff",
        password_hash=hash_password("staff2026!"),
        must_change_password=False,
        is_active=True,
        is_superadmin=False,
    )
    session.add(staff)
    session.flush()
    session.add(StaffDepartmentScope(staff_user_id=21, department_id=1))
    session.commit()
    session.close()

    client = TestClient(app)
    login_response = client.post(
        "/auth/login",
        json={"email": "scope.blocked@example.com", "password": "staff2026!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/staff/mobile/daily",
        params={"department_id": 2, "start_date": "2026-03-09", "end_date": "2026-03-15"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_staff_mobile_daily_rejects_non_monday_sunday_period():
    seed_data()
    session = TestingSessionLocal()
    staff = StaffUser(
        id=22,
        email="scope.period@example.com",
        full_name="Period Staff",
        password_hash=hash_password("staff2026!"),
        must_change_password=False,
        is_active=True,
        is_superadmin=False,
    )
    session.add(staff)
    session.flush()
    session.add(StaffDepartmentScope(staff_user_id=22, department_id=1))
    session.commit()
    session.close()

    client = TestClient(app)
    login_response = client.post(
        "/auth/login",
        json={"email": "scope.period@example.com", "password": "staff2026!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/staff/mobile/daily",
        params={"department_id": 1, "start_date": "2026-03-10", "end_date": "2026-03-16"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_staff_mobile_lists_department_employees():
    seed_data()
    session = TestingSessionLocal()
    staff = StaffUser(
        id=23,
        email="scope.employees@example.com",
        full_name="Employees Staff",
        password_hash=hash_password("staff2026!"),
        must_change_password=False,
        is_active=True,
        is_superadmin=False,
    )
    session.add(staff)
    session.flush()
    session.add(StaffDepartmentScope(staff_user_id=23, department_id=1))
    session.commit()
    session.close()

    client = TestClient(app)
    login_response = client.post(
        "/auth/login",
        json={"email": "scope.employees@example.com", "password": "staff2026!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/staff/mobile/employees",
        params={"department_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["name"] == "Ana García"


def test_staff_mobile_employee_year_returns_ytd_2026_summary():
    seed_data()
    session = TestingSessionLocal()
    current_week_monday = date.today() - timedelta(days=date.today().weekday())
    previous_week_monday = current_week_monday - timedelta(days=7)
    previous_week_dates = [previous_week_monday + timedelta(days=offset) for offset in range(3)]
    employee_events = (
        session.query(AttendanceEvent)
        .filter(AttendanceEvent.employee_id == 1)
        .order_by(AttendanceEvent.id.asc())
        .all()
    )
    for event, event_date in zip(employee_events, previous_week_dates, strict=False):
        event.fecha = event_date
        event.event_ts = datetime.combine(event_date, event.tiempo)
        event.created_at = datetime.combine(event_date, event.tiempo)

    monday_schedule = session.query(Schedule).filter(Schedule.employee_id == 1).first()
    assert monday_schedule is not None
    monday_schedule.dia_letra = DAY_LABELS[previous_week_dates[0].weekday()]
    session.add_all([
        Schedule(
            id=2,
            employee_id=1,
            nombre="Entrada",
            esc_clave="CME",
            prog_clave="CME",
            dia_letra=DAY_LABELS[previous_week_dates[1].weekday()],
            inicio=time(7, 0),
            fin=time(9, 0),
        ),
        Schedule(
            id=3,
            employee_id=1,
            nombre="Entrada",
            esc_clave="CME",
            prog_clave="CME",
            dia_letra=DAY_LABELS[previous_week_dates[2].weekday()],
            inicio=time(7, 0),
            fin=time(9, 0),
        ),
    ])
    staff = StaffUser(
        id=24,
        email="scope.year@example.com",
        full_name="Year Staff",
        password_hash=hash_password("staff2026!"),
        must_change_password=False,
        is_active=True,
        is_superadmin=False,
    )
    session.add(staff)
    session.flush()
    session.add(StaffDepartmentScope(staff_user_id=24, department_id=1))
    session.commit()
    session.close()

    client = TestClient(app)
    login_response = client.post(
        "/auth/login",
        json={"email": "scope.year@example.com", "password": "staff2026!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/staff/mobile/employee-year",
        params={"department_id": 1, "employee_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["employee_id"] == 1
    assert payload["employee_name"] == "Ana García"
    assert payload["report_year"] == 2026
    assert payload["total_days"] == 3
    assert payload["late_days"] == 0
    assert payload["punctuality_rate"] == pytest.approx(0.0, rel=0, abs=0.01)
    assert payload["registered_schedule_intervals"]
    assert payload["weeks"]
    previous_week_sunday = (date.today() - timedelta(days=date.today().weekday() + 1)).isoformat()
    assert payload["window_end"] == previous_week_sunday
    first_week = payload["weeks"][0]
    assert first_week["days"]
    assert any(day["status"] == "absence" for day in first_week["days"])
    assert "last_event" in first_week["days"][0]
    assert "scheduled_start" in first_week["days"][0]


def test_staff_mobile_infers_single_event_as_exit_when_closer_to_schedule_end():
    seed_data()
    today = date.today()
    session = TestingSessionLocal()
    session.query(AttendanceEvent).filter(AttendanceEvent.employee_id == 1).delete()
    session.add(
        AttendanceEvent(
            id=500,
            employee_id=1,
            nombre="Ana García",
            departamento_raw="Escuela Modelo/Mérida/CME-Ingeniería",
            device_name="R1",
            device_serial="SINGLE-EXIT",
            source="test",
            fecha=today,
            tiempo=time(14, 4),
            event_ts=datetime.combine(today, time(14, 4)),
            created_at=datetime.combine(today, time(14, 4)),
        )
    )
    staff = StaffUser(
        id=26,
        email="scope.singleexit@example.com",
        full_name="Single Exit Staff",
        password_hash=hash_password("staff2026!"),
        must_change_password=False,
        is_active=True,
        is_superadmin=False,
    )
    session.add(staff)
    session.flush()
    session.add(StaffDepartmentScope(staff_user_id=26, department_id=1))
    session.commit()
    session.close()

    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    client = TestClient(app)
    login_response = client.post(
        "/auth/login",
        json={"email": "scope.singleexit@example.com", "password": "staff2026!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/staff/mobile/daily",
        params={"department_id": 1, "start_date": str(monday), "end_date": str(sunday)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = response.json()
    target_day = next(day for day in rows[0]["days"] if day["date"] == str(today))
    assert target_day["status"] == "absence"
    assert target_day["first_event"] == "14:04:00"
    assert target_day["entry_event"] is None
    assert target_day["exit_event"] == "14:04:00"
    assert target_day["entry_event_inferred"] is False
    assert target_day["exit_event_inferred"] is True


def test_staff_mobile_preserves_split_schedule_and_merges_consecutive_blocks():
    seed_data()
    today = date.today()
    session = TestingSessionLocal()
    session.add_all([
        Schedule(
            id=2,
            employee_id=1,
            nombre="Bloque consecutivo",
            esc_clave="CME",
            prog_clave="CME",
            dia_letra=DAY_LABELS[today.weekday()],
            inicio=time(9, 5),
            fin=time(11, 0),
        ),
        Schedule(
            id=3,
            employee_id=1,
            nombre="Bloque mixto",
            esc_clave="CME",
            prog_clave="CME",
            dia_letra=DAY_LABELS[today.weekday()],
            inicio=time(13, 0),
            fin=time(15, 0),
        ),
    ])
    staff = StaffUser(
        id=25,
        email="scope.mixed@example.com",
        full_name="Mixed Staff",
        password_hash=hash_password("staff2026!"),
        must_change_password=False,
        is_active=True,
        is_superadmin=False,
    )
    session.add(staff)
    session.flush()
    session.add(StaffDepartmentScope(staff_user_id=25, department_id=1))
    session.commit()
    session.close()

    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    client = TestClient(app)
    login_response = client.post(
        "/auth/login",
        json={"email": "scope.mixed@example.com", "password": "staff2026!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/staff/mobile/daily",
        params={"department_id": 1, "start_date": str(monday), "end_date": str(sunday)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = response.json()
    scheduled_day = next(day for day in rows[0]["days"] if day["schedule_intervals"])
    assert scheduled_day["has_mixed_schedule"] is True
    assert len(scheduled_day["schedule_intervals"]) == 2
    assert scheduled_day["schedule_intervals"][0]["start"] == "07:00:00"
    assert scheduled_day["schedule_intervals"][0]["end"] == "11:00:00"
    assert scheduled_day["schedule_intervals"][1]["start"] == "13:00:00"
    assert scheduled_day["schedule_intervals"][1]["end"] == "15:00:00"