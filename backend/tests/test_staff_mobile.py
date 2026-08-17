from datetime import date, datetime, time

from fastapi.testclient import TestClient

from app.main import app
from app.models.attendance_event import AttendanceEvent
from app.models.employee import Employee
from app.models.employee_credential import EmployeeCredential
from app.models.staff_access import Department, DepartmentAlias, EmployeeDepartment, StaffDepartmentScope, StaffUser
from app.models.staff_schedule import StaffSemesterSchedule, StaffSemesterScheduleInterval
from app.models.schedule import Schedule
from app.security import hash_password
from tests.conftest import TestingSessionLocal


def seed_staff_mobile_data() -> None:
    session = TestingSessionLocal()
    session.query(AttendanceEvent).delete()
    session.query(Schedule).delete()
    session.query(StaffDepartmentScope).delete()
    session.query(StaffSemesterScheduleInterval).delete()
    session.query(StaffSemesterSchedule).delete()
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
