"""Current departure status; never changes stored attendance or assignments."""
import re
import unicodedata
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import with_loader_criteria
from app.models.employee import Employee
from app.models.attendance_event import AttendanceEvent
from app.models.staff_access import Department, EmployeeDepartment


def is_baja_label(value: str | None) -> bool:
    value = ''.join(c for c in unicodedata.normalize('NFKD', value or '') if not unicodedata.combining(c))
    value = re.sub(r'[^A-Z0-9]+', ' ', value.upper()).strip()
    return bool(re.search(r'(?:^| )BAJAS(?: NOMINA)?$', value))


def is_baja_department(department) -> bool:
    return any(is_baja_label(getattr(department, key, None)) for key in ('name', 'code', 'campus'))


def eligibility_snapshot(db):
    employees = list(db.execute(select(Employee.id, Employee.nombre, Employee.email, Employee.departamento, Employee.campus).order_by(Employee.id)))
    links = list(db.execute(select(EmployeeDepartment.employee_id, EmployeeDepartment.department_id,
        EmployeeDepartment.is_primary, Department.name, Department.code, Department.campus)
        .join(Department, Department.id == EmployeeDepartment.department_id)
        .order_by(EmployeeDepartment.employee_id, EmployeeDepartment.department_id)))
    excluded = {r.id for r in employees if is_baja_label(r.departamento) or is_baja_label(r.campus)}
    excluded.update(r.employee_id for r in links if any(is_baja_label(v) for v in (r.name, r.code, r.campus)))
    # Includes assignments so reactivation and department edits cannot reuse stale totals.
    fingerprint = hashlib.sha256(repr((str(db.get_bind().url), employees, links)).encode()).hexdigest()
    return sorted(excluded), fingerprint


def report_employee_clause(db):
    return Employee.id.not_in(eligibility_snapshot(db)[0])


def report_statement(db, statement):
    """Restrict ORM report SELECTs before aggregation, ordering and pagination."""
    if not statement.is_select:
        return statement
    excluded, _ = eligibility_snapshot(db)
    return statement.options(
        with_loader_criteria(Employee, Employee.id.not_in(excluded), include_aliases=True),
        with_loader_criteria(AttendanceEvent, AttendanceEvent.employee_id.not_in(excluded), include_aliases=True),
    )
