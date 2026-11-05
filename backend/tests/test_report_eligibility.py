from datetime import date, time, datetime
import pytest
from sqlalchemy import select, func
from tests.test_labor_contracts import db  # noqa: F401
from app.models import Employee, Department, EmployeeDepartment, AttendanceEvent
from app.services.report_eligibility import is_baja_label, report_statement, eligibility_snapshot
from app.services.analytics import AnalyticsService
from app.services.labor_contracts import reconciliation
from app.api.routes.employee_management import EmployeeWrite, save, serialize
from fastapi import HTTPException
from tests.test_campus_hours import client, authorize  # noqa: F401


@pytest.mark.parametrize('label', ['BAJAS', 'Bájas_Nómina', 'Escuela Modelo / BAJAS-NOMINA', 'cme-bajas'])
def test_label_normalization(label):
    assert is_baja_label(label)


@pytest.mark.parametrize('label', ['BAJAS MÉDICAS', 'CME-Pasantes', 'Consma Clean', 'Soluciones Castro', 'Rebajas'])
def test_not_global_exclusions(label):
    assert not is_baja_label(label)


@pytest.mark.parametrize('location', ['department', 'campus', 'assignment'])
def test_historical_reports_and_reactivation(db, location):
    employee = db.get(Employee, 1)
    employee.email = 'ana@example.com'
    employee.departamento, employee.campus = 'CME-DTI', 'Mérida'
    day = date(2026, 8, 3)
    db.add(AttendanceEvent(id=1, employee_id=1, nombre=employee.nombre, fecha=day, tiempo=time(7), event_ts=datetime(2026, 8, 3, 7)))
    db.add(Department(id=99, code='bajas_nomina', name='BAJAS NÓMINA'))
    db.commit()
    analytics = AnalyticsService(db)
    before = eligibility_snapshot(db)[1]
    assert len(analytics.staff_period_attendance(period_start=day, period_end=day, department_id=3)) == 1
    # Warm cached reports; a status change must not return their old rows.
    assert any(r.id == 1 for r in analytics.employee_rankings())
    if location == 'department': employee.departamento = 'BAJAS'
    elif location == 'campus': employee.campus = 'BAJAS NOMINA'
    else: db.add(EmployeeDepartment(employee_id=1, department_id=99, is_primary=False))
    db.commit()
    assert eligibility_snapshot(db)[1] != before
    assert analytics.staff_period_attendance(period_start=day, period_end=day, department_id=3) == []
    assert analytics.staff_daily_attendance(target_date=day, department_id=3) == []
    assert analytics.employee_attendance_record(1) is None
    assert not any(r.id == 1 for r in analytics.employee_rankings())
    assert reconciliation(db, [3])['rows'] == []
    assert db.scalar(report_statement(db, select(func.count()).select_from(AttendanceEvent))) == 0
    assert db.scalar(select(func.count()).select_from(AttendanceEvent)) == 1
    assert serialize(employee)['is_departed']
    save(db, employee, EmployeeWrite(nombre=employee.nombre, email=employee.email, department_ids=[3], primary_department_id=3))
    assert not serialize(employee)['is_departed']
    assert len(analytics.staff_period_attendance(period_start=day, period_end=day, department_id=3)) == 1
    assert analytics.employee_attendance_record(1) is not None
    assert db.scalar(select(func.count()).select_from(AttendanceEvent)) == 1


def test_mixed_assignment_rejected_and_exclusive_baja_saved(db):
    db.add(Department(id=99, code='bajas', name='BAJAS', campus='BAJAS')); db.commit()
    employee = db.get(Employee, 1)
    employee.email = 'ana@example.com'
    payload = dict(nombre=employee.nombre, email=employee.email, department_ids=[3, 99], primary_department_id=99)
    with pytest.raises(HTTPException) as exc:
        save(db, employee, EmployeeWrite(**payload))
    assert exc.value.status_code == 422
    result = save(db, employee, EmployeeWrite(**(payload | {'department_ids': [99]})))
    assert result['department_ids'] == [99] and result['primary_department_id'] == 99
    assert result['is_departed'] and result['campus'] == 'BAJAS'


@pytest.mark.parametrize('assignment_only', [False, True])
def test_import_preserves_baja_with_legacy_operating_link(db, assignment_only):
    from app.services.attendance_import import AttendanceImportService, ParsedAttendanceRow
    from app.core.config import get_settings
    employee = db.get(Employee, 1)
    employee.departamento, employee.campus = 'BAJAS', 'BAJAS'
    if assignment_only:
        employee.departamento, employee.campus = 'CME-DTI', 'Mérida'
        db.add(Department(id=99, code='bajas', name='BAJAS'))
        db.add(EmployeeDepartment(employee_id=1, department_id=99, is_primary=False))
    db.commit()
    service = AttendanceImportService(db=db, settings=get_settings())
    row = ParsedAttendanceRow(1, 1, employee.nombre, 'CME-DTI', date(2026, 11, 4), time(7), None, None, None)
    assert service._ensure_employees([row]) == []
    assert service._persist_attendance_rows([row])[0] == 1
    db.flush()
    assert employee.departamento == ('CME-DTI' if assignment_only else 'BAJAS')
    assert sorted(x.department_id for x in employee.department_links) == ([3, 99] if assignment_only else [3])
    assert db.scalar(select(func.count()).select_from(AttendanceEvent)) == 1
    assert eligibility_snapshot(db)[0] == [1]


def test_report_selectors_direct_urls_and_management_visibility(db, client):
    authorize(db, 'gaibarra@hotmail.com')
    db.get(Employee, 1).departamento = 'BAJAS NOMINA'
    db.commit()
    result = client.get('/staff/mobile/employees', params={'department_id': 3})
    assert result.status_code == 200 and result.json() == []
    result = client.get('/staff/mobile/employee-year', params={'department_id': 3, 'employee_id': 1})
    assert result.status_code == 404 and 'disponible para reportes' in result.json()['detail']
    result = client.get('/employees/manage', params={'q': 'PÉREZ'})
    assert result.status_code == 200 and result.json()['total'] == 1
    assert result.json()['items'][0]['is_departed']


def test_filter_precedes_pagination(db):
    db.get(Employee, 1).departamento = 'BAJAS'
    db.get(Employee, 1).nombre = 'AAA'
    db.commit()
    rows = db.scalars(report_statement(db, select(Employee).order_by(Employee.nombre).limit(1))).all()
    assert [e.id for e in rows] == [2]


def test_edit_baja_preserves_imported_placeholder_and_rejects_mixed_payload(db, client):
    authorize(db, 'gaibarra@hotmail.com')
    db.add(Department(id=99, code='bajas', name='BAJAS')); db.commit()
    employee = db.get(Employee, 1)
    payload = dict(nombre=employee.nombre, email=employee.email, department_ids=[3, 99], primary_department_id=99)
    assert client.put('/employees/manage/1', json=payload).status_code == 422
    result = client.put('/employees/manage/1', json=payload | {'department_ids': [99]})
    assert result.status_code == 200, result.text
    assert result.json()['email'] == 'emp-1@pendiente.local'
    assert result.json()['is_departed']
    result = client.put('/employees/manage/1', json=payload | {'department_ids': [3], 'primary_department_id': 3})
    assert result.status_code == 200 and not result.json()['is_departed']
