"""Authentication dependencies and authorization guards."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.bootstrap import has_staff_access_schema
from app.db.session import get_db
from app.models.employee_credential import EmployeeCredential
from app.models.employee import Employee
from app.models.staff_access import StaffDepartmentScope, StaffUser
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedEmployee:
    employee: Employee
    must_change_password: bool
    is_admin: bool


@dataclass
class AuthenticatedStaff:
    staff_user: StaffUser
    department_ids: set[int]


@dataclass
class AuthenticatedActor:
    actor_type: str
    is_admin: bool
    must_change_password: bool
    employee: Employee | None = None
    staff: StaffUser | None = None
    department_ids: set[int] | None = None

    @property
    def is_staff(self) -> bool:
        return self.actor_type == "staff"

    @property
    def is_employee(self) -> bool:
        return self.actor_type == "employee"

    @property
    def is_superadmin(self) -> bool:
        return bool(self.staff and self.staff.is_superadmin)

    def can_access_department(self, department_id: int) -> bool:
        if self.is_superadmin:
            return True
        return bool(self.department_ids and department_id in self.department_ids)


def get_current_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedActor:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")
    payload = decode_access_token(credentials.credentials, settings.auth_secret_key)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida o expirada")
    actor_type = payload.get("actor_type")
    subject_id = payload.get("sub")
    if actor_type not in {"employee", "staff"} or not isinstance(subject_id, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    if actor_type == "employee":
        row = (
            db.query(Employee, EmployeeCredential)
            .join(EmployeeCredential, EmployeeCredential.employee_id == Employee.id)
            .filter(Employee.id == subject_id)
            .first()
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
        employee, credential = row
        is_admin = employee.email.strip().lower() == settings.admin_email.strip().lower()
        return AuthenticatedActor(
            actor_type="employee",
            employee=employee,
            staff=None,
            must_change_password=credential.must_change_password,
            is_admin=is_admin,
            department_ids=None,
        )

    if not has_staff_access_schema(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Las tablas de staff aún no están disponibles en la base de datos",
        )

    staff_row = db.query(StaffUser).filter(StaffUser.id == subject_id, StaffUser.is_active.is_(True)).first()
    if staff_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    scope_ids = {
        int(department_id)
        for (department_id,) in db.query(StaffDepartmentScope.department_id)
        .filter(StaffDepartmentScope.staff_user_id == staff_row.id)
        .all()
    }
    return AuthenticatedActor(
        actor_type="staff",
        employee=staff_row.employee,
        staff=staff_row,
        must_change_password=staff_row.must_change_password,
        is_admin=staff_row.is_superadmin,
        department_ids=scope_ids,
    )


def get_current_employee(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedEmployee:
    if not actor.is_employee or actor.employee is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso disponible solo para empleados")
    return AuthenticatedEmployee(
        employee=actor.employee,
        must_change_password=actor.must_change_password,
        is_admin=actor.is_admin,
    )


def require_password_change_completed(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    return actor


def require_admin_employee(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    if not actor.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso restringido al administrador")
    return actor


def require_superadmin_actor(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    if not actor.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso disponible solo para superadministradores")
    return actor


def require_staff_actor(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    if not actor.is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso disponible solo para staff")
    return actor