from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.dependencies.auth import get_current_actor, AuthenticatedActor
from app.models.staff_access import Department, EmployeeDepartment
from app.models.employee_credential import EmployeeCredential  # noqa: F401


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add_all(
            [
                Department(id=1, code="a", name="Administración", campus="Mérida"),
                Department(id=2, code="b", name="Docencia", campus="Valladolid"),
            ]
        )
        db.commit()

    def get_session():
        with factory() as db:
            yield db

    old = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = get_session
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor(
        actor_type="staff",
        is_admin=True,
        must_change_password=False,
        staff=SimpleNamespace(email="gaibarra@hotmail.com"),
    )
    with TestClient(app) as c:
        yield c, factory
    app.dependency_overrides.clear()
    app.dependency_overrides.update(old)
    engine.dispose()


payload = dict(
    nombre="Ana García",
    email="ana@example.com",
    department_ids=[1, 2],
    primary_department_id=1,
    external_employee_id=88,
)


def test_crud_and_assignments(client):
    c, factory = client
    created = c.post("/employees/manage", json=payload)
    assert created.status_code == 201, created.text
    eid = created.json()["id"]
    assert created.json()["campus"] == "Mérida"
    assert c.get("/employees/manage?q=García").json()["total"] == 1
    assert c.get("/employees/manage?department_id=2").json()["total"] == 1
    assert c.get(f"/employees/manage/{eid}").json()["nombre"] == "Ana García"
    changed = c.put(
        f"/employees/manage/{eid}",
        json={**payload, "department_ids": [2], "primary_department_id": 2},
    )
    assert changed.status_code == 200
    assert changed.json()["campus"] == "Valladolid"
    with factory() as db:
        assert len(db.scalars(select(EmployeeDepartment)).all()) == 1
    assert c.delete(f"/employees/manage/{eid}").status_code == 204
    assert c.get(f"/employees/manage/{eid}").status_code == 404


@pytest.mark.parametrize("actor_type", ["staff", "employee"])
def test_other_admin_denied(client, actor_type):
    c, _ = client
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor(
        actor_type=actor_type,
        is_admin=True,
        must_change_password=False,
        **{actor_type: SimpleNamespace(email="other@example.com")},
    )
    for method, path in [
        ("get", ""),
        ("get", "/departments"),
        ("get", "/1"),
        ("post", ""),
        ("put", "/1"),
        ("delete", "/1"),
    ]:
        r = getattr(c, method)(
            "/employees/manage" + path, **({"json": payload} if method in ("post", "put") else {})
        )
        assert r.status_code == 403


def test_conflicts_validation_and_owner(client):
    c, _ = client
    assert c.post("/employees/manage", json=payload).status_code == 201
    assert c.post("/employees/manage", json=payload).status_code == 409
    assert (
        c.post("/employees/manage", json={**payload, "email": "b@example.com"}).status_code == 409
    )
    assert c.post("/employees/manage", json={**payload, "department_ids": [999]}).status_code == 422
    assert c.post("/employees/manage", json={**payload, "nombre": "  "}).status_code == 422
    own = c.post(
        "/employees/manage",
        json={**payload, "email": "gaibarra@hotmail.com", "external_employee_id": None},
    )
    eid = own.json()["id"]
    assert c.delete(f"/employees/manage/{eid}").status_code == 409
    assert (
        c.put(
            f"/employees/manage/{eid}", json={**payload, "email": "changed@example.com"}
        ).status_code
        == 409
    )


def test_historical_data_preserved(client):
    from datetime import date
    from app.models.staff_attendance_exemption import StaffAttendanceExemption

    c, factory = client
    eid = c.post("/employees/manage", json=payload).json()["id"]
    with factory() as db:
        db.add(
            StaffAttendanceExemption(
                employee_id=eid,
                department_id=1,
                target_date=date(2026, 10, 8),
                reason="fuerza_mayor",
                exempt_entry=True,
                exempt_exit=True,
            )
        )
        db.commit()
    assert c.delete(f"/employees/manage/{eid}").status_code == 409
    assert c.get(f"/employees/manage/{eid}").status_code == 200


def test_unauthenticated_denied(client):
    c, _ = client
    del app.dependency_overrides[get_current_actor]
    assert c.get("/employees/manage").status_code == 401
    assert c.post("/employees/manage", json=payload).status_code == 401


def test_owner_employee_access(client):
    c, _ = client
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor(
        actor_type="employee",
        is_admin=True,
        must_change_password=False,
        employee=SimpleNamespace(email="GAIBARRA@hotmail.com"),
    )
    assert c.get("/employees/manage").status_code == 200
    assert c.post("/employees/manage", json=payload).status_code == 201
