from datetime import date, time
import json
from types import SimpleNamespace
import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.dependencies.auth import require_staff_actor, get_current_actor, AuthenticatedActor
from app.models import Employee, Department, EmployeeDepartment, StaffUser, StaffSemesterSchedule, StaffSemesterScheduleInterval, LaborContract, LaborContractImport, AttendanceImportBatch
from app.services.labor_contract_import import preview, apply_preview, rollback, read_source, export_review
from app.services.labor_contracts import semester_minutes, comparison, covering_contract, enrich_weekly, reconciliation


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as session:
        session.add_all([
            StaffUser(id=10, email="staff@test.test", full_name="Operador", password_hash="not-used", is_active=True, is_superadmin=True),
            Department(id=3, code="CME-DTI", name="CME-DTI", campus="Mérida"),
            Department(id=4, code="CCH-DTI", name="CCH-DTI", campus="Chetumal"),
            Employee(id=1, nombre="PÉREZ GÓMEZ ANA", email="emp-1@pendiente.local", departamento="", campus=None),
            Employee(id=2, nombre="OTRA PERSONA", email="otro@test.test", departamento="CCH-DTI", campus="Chetumal"),
            EmployeeDepartment(employee_id=1, department_id=3, is_primary=True),
            EmployeeDepartment(employee_id=2, department_id=4, is_primary=True),
        ])
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def source(tmp_path):
    def make(name="PEREZ GOMEZ ANA", email="ana@test.test", hours=40, key=999, filename="source.xlsx"):
        book = Workbook()
        book.remove(book.active)
        for title in ["escuela", "universidad", "valladolid", "chetumal"]:
            ws = book.create_sheet(title)
            ws.append(["Clave", "Nombre completo", "RFC", "CURP", "Correo electrónico", "Descripción", "Cve Depto", "No. Afil. IMSS", "Fecha de alta", "HORAS CONTRATADAS"])
            if title == "universidad":
                ws.append([key, name, "SENSITIVE_RFC", "SENSITIVE_CURP", email, "DTI", 999, "SENSITIVE_IMSS", "2000-01-01", hours])
        path = tmp_path / filename
        book.save(path)
        return path
    return make


def test_preview_exact_accent_does_not_use_excel_id_or_import_sensitive_fields(db, source, tmp_path):
    path = source(key=2)
    result = preview(db, path)
    row = result["rows"][0]
    assert row["employee_id"] == 1
    assert row["changes"] == {"email": "ana@test.test", "campus": "Mérida"}
    assert db.get(Employee, 1).email == "emp-1@pendiente.local"
    assert not list(db.scalars(select(LaborContract)))
    assert "SENSITIVE" not in json.dumps(result)
    assert "2000-01-01" not in json.dumps(result)
    output = tmp_path / "review.xlsx"
    export_review(output, result)
    assert output.stat().st_mode & 0o777 == 0o600


def test_conflicting_email_blocks_matching_and_confirmation(db, source):
    path = source(email="otro@test.test")
    result = preview(db, path)
    assert result["rows"][0]["employee_id"] is None
    assert not result["rows"][0]["eligible"]
    confirmed = preview(db, path, confirmed_matches={"universidad:2": 1})
    assert confirmed["rows"][0]["errors"]


def test_confirmed_profile_is_preserved_and_unknown_not_created(db, source):
    employee = db.get(Employee, 1)
    employee.email, employee.campus = "confirmed@test.test", "Montejo"
    db.commit()
    row = preview(db, source())["rows"][0]
    assert not row["changes"]
    assert len(row["warnings"]) == 2
    pending = preview(db, source(name="PERSONA COMPLETAMENTE DIFERENTE", email="new@test.test"))
    assert pending["summary"]["pending_identity"] == 1
    assert len(list(db.scalars(select(Employee)))) == 2


@pytest.mark.parametrize("hours,minutes", [(None, None), (37.5, 2250), (0, 0), ("40", 2400)])
def test_contract_hours_parse(source, hours, minutes):
    assert read_source(source(hours=hours))[0]["weekly_minutes"] == minutes


@pytest.mark.parametrize("hours", [-1, "sin datos", 999, 1.001])
def test_invalid_hours_block(source, hours):
    assert read_source(source(hours=hours))[0]["errors"]


def test_apply_idempotent_audited_and_reversible(db, source):
    path = source()
    saved = preview(db, path)
    receipt_id = apply_preview(db, path, saved, ["universidad:2"], 10)
    db.commit()
    assert db.get(Employee, 1).email == "ana@test.test"
    contract = db.scalar(select(LaborContract))
    assert contract.weekly_minutes == 2400
    assert contract.valid_from == date(2026, 8, 1)
    assert apply_preview(db, path, saved, ["universidad:2"], 10) == receipt_id
    assert len(list(db.scalars(select(LaborContract)))) == 1
    rollback(db, receipt_id, 10)
    db.commit()
    assert db.get(Employee, 1).email == "emp-1@pendiente.local"
    assert not db.get(LaborContract, contract.id).active
    assert db.get(LaborContractImport, receipt_id).reverted_at
    assert len(list(db.scalars(select(Employee)))) == 2


def test_blank_hours_preserve_existing_contract(db, source):
    path = source()
    apply_preview(db, path, preview(db, path), ["universidad:2"], 10)
    db.commit()
    path = source(hours=None, filename="new.xlsx")
    apply_preview(db, path, preview(db, path), ["universidad:2"], 10)
    db.commit()
    assert len(list(db.scalars(select(LaborContract)))) == 1
    assert db.scalar(select(LaborContract)).active


def test_corrections_preserve_history_and_rollback_prior_contract(db, source):
    path = source()
    apply_preview(db, path, preview(db, path), ["universidad:2"], 10)
    db.commit()
    path = source(hours=35)
    receipt_id = apply_preview(db, path, preview(db, path), ["universidad:2"], 10)
    db.commit()
    assert len(list(db.scalars(select(LaborContract)))) == 2
    assert db.scalar(select(LaborContract).where(LaborContract.active.is_(True))).weekly_minutes == 2100
    rollback(db, receipt_id, 10)
    db.commit()
    assert db.scalar(select(LaborContract).where(LaborContract.active.is_(True))).weekly_minutes == 2400


def test_stale_preview_and_modified_contract_prevent_overwrites(db, source):
    path = source()
    saved = preview(db, path)
    db.get(Employee, 1).nombre = "NUEVO NOMBRE"
    db.commit()
    with pytest.raises(ValueError, match="cambiaron"):
        apply_preview(db, path, saved, ["universidad:2"], 10)
    db.rollback()
    db.get(Employee, 1).nombre = "PÉREZ GÓMEZ ANA"
    db.commit()
    receipt_id = apply_preview(db, path, preview(db, path), ["universidad:2"], 10)
    db.commit()
    db.scalar(select(LaborContract)).weekly_minutes = 2300
    db.commit()
    with pytest.raises(ValueError, match="posteriores"):
        rollback(db, receipt_id, 10)


def test_semester_comparison_merges_blocks_and_ignores_daily_exceptions():
    block = lambda day, a, b: SimpleNamespace(weekday=day, start=time(*a), end=time(*b))
    schedule = SimpleNamespace(intervals=[block(0, (7, 0), (12, 0)), block(0, (7, 0), (12, 0)), block(0, (13, 0), (16, 0)), block(1, (7, 0), (15, 0))])
    assert semester_minutes(schedule) == 16 * 60
    assert comparison(None, 0) == "pending_contract"
    assert comparison(2400, None) == "no_schedule"
    assert comparison(2400, 2400) == "matches"
    assert comparison(2400, 2300) == "lower"
    assert comparison(2400, 2500) == "higher"


def test_week_crossing_contract_boundary_has_no_reference(db, source):
    path = source()
    apply_preview(db, path, preview(db, path), ["universidad:2"], 10)
    db.commit()
    rows = [dict(employee_id=1, contracted_seconds=35*3600, difference_seconds=-3600)]
    enrich_weekly(db, rows, date(2026, 9, 28), date(2026, 10, 4))
    assert rows[0]["labor_contract_seconds"] == 40*3600
    assert rows[0]["scheduled_contract_difference_seconds"] == -5*3600
    enrich_weekly(db, rows, date(2026, 7, 27), date(2026, 8, 2))
    assert rows[0]["labor_contract_seconds"] is None
    assert rows[0]["scheduled_contract_difference_seconds"] is None


def test_multiple_departments_keep_same_person_hours(db, source):
    path = source()
    apply_preview(db, path, preview(db, path), ["universidad:2"], 10)
    db.add(EmployeeDepartment(employee_id=1, department_id=4, is_primary=False))
    db.commit()
    result = reconciliation(db, [3, 4])
    rows = [r for r in result["rows"] if r["employee_id"] == 1]
    assert len(rows) == 2
    assert [r["contract_minutes"] for r in rows] == [2400, 2400]


def test_report_api_scope_and_export(db):
    old = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_staff_actor] = lambda: AuthenticatedActor(actor_type="staff", is_admin=False, must_change_password=False, department_ids={3})
    try:
        with TestClient(app) as client:
            response = client.get("/staff/labor-contracts")
            assert response.status_code == 200
            assert [r["employee_id"] for r in response.json()["rows"]] == [1]
            assert client.get("/staff/labor-contracts?department_id=4").status_code == 403
            assert client.get("/staff/labor-contracts?department_id=3&employee_id=2").status_code == 404
            assert client.get("/staff/labor-contracts?contract_status=invalid").status_code == 400
            export = client.get("/staff/labor-contracts?export=true")
            assert export.status_code == 200
            assert "OTRA PERSONA" not in export.text
            assert "filename=" in export.headers["content-disposition"]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def test_endpoint_requires_staff_not_employee(db):
    old = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            assert client.get("/staff/labor-contracts").status_code == 401
            app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor(actor_type="employee", is_admin=False, must_change_password=False, employee=db.get(Employee, 1))
            assert client.get("/staff/labor-contracts").status_code == 403
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def test_import_requires_superadmin(db, source):
    path = source()
    saved = preview(db, path)
    db.get(StaffUser, 10).is_superadmin = False
    db.commit()
    with pytest.raises(ValueError, match="superadministrador"):
        apply_preview(db, path, saved, ["universidad:2"], 10)


def test_audited_provisional_name_can_change_after_explicit_confirmation(db, source):
    employee = db.get(Employee, 1)
    employee.nombre = "ANA PEREZ GOMEZ PEREZ GOMEZ"
    db.add(AttendanceImportBatch(id="audit", original_filename="old.xlsx", total_rows=1, imported_rows=1,
           skipped_duplicates=0, invalid_rows=0, auto_created_employees=[{"employee_id": 1, "nombre": employee.nombre}]))
    db.commit()
    path = source()
    assert preview(db, path)["rows"][0]["employee_id"] is None
    result = preview(db, path, confirmed_matches={"universidad:2": 1})
    assert result["rows"][0]["changes"]["nombre"] == "PEREZ GOMEZ ANA"


def test_invalid_department_mapping_and_tampered_preview_block(db, source):
    path = source()
    assert preview(db, path, department_map={"universidad:999": 4})["rows"][0]["errors"]
    saved = preview(db, path)
    saved["rows"][0]["weekly_minutes"] = 1000
    with pytest.raises(ValueError, match="cambiaron"):
        apply_preview(db, path, saved, ["universidad:2"], 10)


def test_rollback_rejects_later_profile_changes(db, source):
    path = source()
    receipt_id = apply_preview(db, path, preview(db, path), ["universidad:2"], 10)
    db.commit()
    db.get(Employee, 1).email = "later@test.test"
    db.commit()
    with pytest.raises(ValueError, match="posteriores"):
        rollback(db, receipt_id, 10)


def test_schema_migration_on_isolated_database():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    import importlib.util
    from pathlib import Path
    path = Path(__file__).parents[1] / "alembic/versions/20261007_0015_labor_contracts.py"
    spec = importlib.util.spec_from_file_location("contract_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert {"labor_contracts", "labor_contract_imports"} <= set(inspect(conn).get_table_names())
            migration.downgrade()
            assert not inspect(conn).get_table_names()
    engine.dispose()
