from datetime import date, datetime, time

from fastapi.testclient import TestClient

from app.main import app
from app.models.attendance_event import AttendanceEvent
from app.models.employee import Employee
from app.models.employee_credential import EmployeeCredential
from app.models.staff_access import Department, DepartmentAlias, EmployeeDepartment, StaffDepartmentScope, StaffUser
from app.security import hash_password
from tests.conftest import TestingSessionLocal


def seed_staff_mobile_data() -> None:
    session = TestingSessionLocal()
    session.query(AttendanceEvent).delete()
    session.query(StaffDepartmentScope).delete()
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