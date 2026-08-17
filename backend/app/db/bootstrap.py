"""Startup helpers to align auth columns and default credentials."""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.models.employee import Employee
from app.models.employee_credential import EmployeeCredential
from app.models.staff_access import Department, DepartmentAlias, EmployeeDepartment, StaffDepartmentScope, StaffUser
from app.security import hash_password
from app.services.department_normalization import canonicalize_department, derive_department_campus

_STAFF_ACCESS_TABLES = {
    "departments",
    "department_aliases",
    "employee_departments",
    "staff_users",
    "staff_department_scopes",
}


def ensure_employee_auth_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "employees" not in table_names or "employee_credentials" in table_names:
        return
    EmployeeCredential.__table__.create(bind=engine, checkfirst=True)


def ensure_staff_access_schema(engine: Engine) -> None:
    if not has_staff_access_schema(engine, require_all=False):
        return
    try:
        for table in (
            Department.__table__,
            DepartmentAlias.__table__,
            EmployeeDepartment.__table__,
            StaffUser.__table__,
            StaffDepartmentScope.__table__,
        ):
            table.create(bind=engine, checkfirst=True)
    except SQLAlchemyError:
        return


def sync_default_employee_passwords(db: Session, settings: Settings) -> None:
    employees = db.query(Employee).all()
    changed = False
    for employee in employees:
        if employee.credential is None:
            db.add(
                EmployeeCredential(
                    employee_id=employee.id,
                    password_hash=hash_password(settings.auth_default_password),
                    must_change_password=True,
                )
            )
            changed = True
        elif employee.credential.must_change_password is None:
            employee.credential.must_change_password = True
            changed = True
    if changed:
        db.commit()


def sync_department_catalog(db: Session) -> None:
    if not has_staff_access_schema(db):
        return
    employees = db.query(Employee).all()
    if not employees:
        return

    alias_map = {
        _normalize_value(alias.alias): alias.department
        for alias in db.query(DepartmentAlias).join(Department).all()
        if _normalize_value(alias.alias)
    }
    changed = False
    for employee in employees:
        canonical_department = canonicalize_department(employee.departamento)
        if canonical_department.canonical_name and employee.departamento != canonical_department.canonical_name:
            employee.departamento = canonical_department.canonical_name
            changed = True
        canonical_campus = canonical_department.campus or derive_department_campus(canonical_department.raw_name)
        if canonical_campus and employee.campus != canonical_campus:
            employee.campus = canonical_campus
            changed = True
        alias_candidates = {
            _normalize_value(alias)
            for alias in canonical_department.aliases
            if _normalize_value(alias)
        }
        if not alias_candidates:
            continue
        department = next((alias_map[alias] for alias in alias_candidates if alias in alias_map), None)
        if department is None:
            campus = (employee.campus or canonical_department.campus or derive_department_campus(employee.departamento)) or None
            department = Department(
                code=_build_department_code(canonical_department.canonical_name),
                name=canonical_department.canonical_name,
                campus=campus,
                active=True,
            )
            db.add(department)
            db.flush()
            for alias_value in canonical_department.aliases:
                db.add(
                    DepartmentAlias(
                        department_id=department.id,
                        alias=alias_value,
                        source="employee",
                    )
                )
                alias_map[_normalize_value(alias_value)] = department
            changed = True
        else:
            for alias_value in canonical_department.aliases:
                normalized_alias = _normalize_value(alias_value)
                if normalized_alias and normalized_alias not in alias_map:
                    db.add(
                        DepartmentAlias(
                            department_id=department.id,
                            alias=alias_value,
                            source="employee",
                        )
                    )
                    alias_map[normalized_alias] = department
                    changed = True
        has_link = any(link.department_id == department.id for link in employee.department_links)
        if not has_link:
            db.add(
                EmployeeDepartment(
                    employee_id=employee.id,
                    department_id=department.id,
                    is_primary=True,
                )
            )
            changed = True
    if changed:
        db.commit()


def sync_default_staff_superadmin(db: Session, settings: Settings) -> None:
    if not has_staff_access_schema(db):
        return
    normalized_admin_email = settings.admin_email.strip().lower()
    if not normalized_admin_email:
        return
    staff_user = db.query(StaffUser).filter(StaffUser.email == normalized_admin_email).first()
    employee = db.query(Employee).filter(Employee.email == normalized_admin_email).first()
    changed = False
    if staff_user is None:
        staff_user = StaffUser(
            email=normalized_admin_email,
            full_name=(employee.nombre if employee else "Superadmin ModeloAsist"),
            password_hash=hash_password(settings.auth_default_password),
            must_change_password=False,
            is_active=True,
            is_superadmin=True,
            employee_id=(employee.id if employee else None),
        )
        db.add(staff_user)
        changed = True
    else:
        if not staff_user.is_superadmin:
            staff_user.is_superadmin = True
            changed = True
        if employee and staff_user.employee_id != employee.id:
            staff_user.employee_id = employee.id
            changed = True
        if not staff_user.is_active:
            staff_user.is_active = True
            changed = True
    if changed:
        db.commit()


def _normalize_value(value: str | None) -> str:
    return (value or "").strip().lower()


def _build_department_code(value: str) -> str:
    normalized = "-".join(chunk.strip() for chunk in value.split("/") if chunk.strip())
    return normalized[:255] or "department"


def _extract_campus(department_name: str | None) -> str | None:
    return derive_department_campus(department_name)


def has_staff_access_schema(bind: Engine | Session, *, require_all: bool = True) -> bool:
    target = bind.get_bind() if isinstance(bind, Session) else bind
    try:
        table_names = set(inspect(target).get_table_names())
    except SQLAlchemyError:
        return False
    if "employees" not in table_names:
        return False
    if require_all:
        return _STAFF_ACCESS_TABLES.issubset(table_names)
    return True