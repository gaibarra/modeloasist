from datetime import date, datetime, time, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.models.attendance_event import AttendanceEvent
from app.models.employee_credential import EmployeeCredential
from app.models.employee import Employee
from app.models.staff_access import Department, DepartmentAlias, EmployeeDepartment, StaffDepartmentScope, StaffUser
from app.security import hash_password
from tests.conftest import TestingSessionLocal


def seed_auth_data(*, must_change_password: bool = True) -> None:
    session = TestingSessionLocal()
    session.query(AttendanceEvent).delete()
    session.query(StaffDepartmentScope).delete()
    session.query(StaffUser).delete()
    session.query(EmployeeDepartment).delete()
    session.query(DepartmentAlias).delete()
    session.query(Department).delete()
    session.query(EmployeeCredential).delete()
    session.query(Employee).delete()

    today = date.today()
    employee = Employee(
        id=1,
        nombre="Ana García",
        departamento="Escuela Modelo/Mérida/CME-Ingeniería",
        campus="Mérida",
        email="ana@example.com",
    )
    admin = Employee(
        id=2,
        nombre="Gerardo Aibarra",
        departamento="Escuela Modelo/Mérida/Rectoría",
        campus="Mérida",
        email="gaibarra@hotmail.com",
    )
    credentials = [
        EmployeeCredential(employee_id=1, password_hash=hash_password("modelo2026"), must_change_password=must_change_password),
        EmployeeCredential(employee_id=2, password_hash=hash_password("modelo2026"), must_change_password=False),
    ]
    departments = [
        Department(id=1, code="merida-ingenieria", name=employee.departamento, campus="Mérida", active=True),
        Department(id=2, code="merida-rectoria", name=admin.departamento, campus="Mérida", active=True),
    ]
    aliases = [
        DepartmentAlias(id=1, department_id=1, alias=employee.departamento, source="employee"),
        DepartmentAlias(id=2, department_id=2, alias=admin.departamento, source="employee"),
    ]
    employee_departments = [
        EmployeeDepartment(employee_id=1, department_id=1, is_primary=True),
        EmployeeDepartment(employee_id=2, department_id=2, is_primary=True),
    ]
    events = [
        AttendanceEvent(
            id=1,
            employee_id=1,
            nombre="Ana García",
            departamento_raw=employee.departamento,
            device_name="R1",
            device_serial="A-1",
            source="test",
            fecha=today,
            tiempo=time(6, 55),
            event_ts=datetime.combine(today, time(6, 55)),
            created_at=datetime.combine(today, time(6, 55)),
        ),
        AttendanceEvent(
            id=2,
            employee_id=1,
            nombre="Ana García",
            departamento_raw=employee.departamento,
            device_name="R1",
            device_serial="A-2",
            source="test",
            fecha=today - timedelta(days=1),
            tiempo=time(7, 12),
            event_ts=datetime.combine(today - timedelta(days=1), time(7, 12)),
            created_at=datetime.combine(today - timedelta(days=1), time(7, 12)),
        ),
    ]
    session.add_all([employee, admin, *credentials, *departments, *aliases, *employee_departments, *events])
    session.commit()
    session.close()


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_flags_first_password_change():
    seed_auth_data(must_change_password=True)
    client = TestClient(app)

    response = client.post("/auth/login", json={"email": "ana@example.com", "password": "modelo2026"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["employee"]["must_change_password"] is True
    assert payload["employee"]["is_admin"] is False


def test_employee_can_access_attendance_with_temporary_password():
    seed_auth_data(must_change_password=True)
    client = TestClient(app)
    headers = auth_headers(client, "ana@example.com", "modelo2026")

    response = client.get("/employees/me/attendance", headers=headers)

    assert response.status_code == 200
    assert response.json()["employee"]["must_change_password"] is True


def test_change_password_unlocks_self_attendance():
    seed_auth_data(must_change_password=True)
    client = TestClient(app)
    headers = auth_headers(client, "ana@example.com", "modelo2026")

    change_response = client.post(
        "/auth/change-password",
        json={"current_password": "modelo2026", "new_password": "modelo2026!nuevo"},
        headers=headers,
    )
    assert change_response.status_code == 200
    assert change_response.json()["must_change_password"] is False

    fresh_headers = auth_headers(client, "ana@example.com", "modelo2026!nuevo")
    attendance_response = client.get("/employees/me/attendance", headers=fresh_headers)

    assert attendance_response.status_code == 200
    payload = attendance_response.json()
    assert payload["employee"]["email"] == "ana@example.com"
    assert len(payload["recent_events"]) == 2


def test_dashboard_is_reserved_for_admin_email():
    seed_auth_data(must_change_password=False)
    client = TestClient(app)
    headers = auth_headers(client, "ana@example.com", "modelo2026")

    response = client.get("/analytics/dashboard", headers=headers)

    assert response.status_code == 403


def test_staff_can_login_and_receive_department_scope():
    seed_auth_data(must_change_password=False)
    session = TestingSessionLocal()
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
    scope = StaffDepartmentScope(staff_user_id=10, department_id=1)
    session.add(staff)
    session.flush()
    session.add(scope)
    session.commit()
    session.close()

    client = TestClient(app)
    response = client.post("/auth/login", json={"email": "staff@example.com", "password": "staff2026!"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["actor_type"] == "staff"
    assert payload["staff"]["department_ids"] == [1]
    assert payload["employee"] is None


def test_staff_can_change_password_and_login_with_new_password():
    seed_auth_data(must_change_password=False)
    session = TestingSessionLocal()
    staff = StaffUser(
        id=11,
        email="staff-change@example.com",
        full_name="Staff Change",
        password_hash=hash_password("staff2026!"),
        must_change_password=True,
        is_active=True,
        is_superadmin=False,
        employee_id=None,
    )
    session.add(staff)
    session.flush()
    session.add(StaffDepartmentScope(staff_user_id=11, department_id=1))
    session.commit()
    session.close()

    client = TestClient(app)
    login_response = client.post("/auth/login", json={"email": "staff-change@example.com", "password": "staff2026!"})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    change_response = client.post(
        "/auth/change-password",
        json={"current_password": "staff2026!", "new_password": "staff2026!nuevo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert change_response.status_code == 200
    assert change_response.json()["must_change_password"] is False

    relogin_response = client.post(
        "/auth/login",
        json={"email": "staff-change@example.com", "password": "staff2026!nuevo"},
    )
    assert relogin_response.status_code == 200
    assert relogin_response.json()["staff"]["must_change_password"] is False