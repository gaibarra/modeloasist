"""Authentication endpoints for employees and staff users."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.bootstrap import has_staff_access_schema
from app.db.session import get_db
from app.dependencies.auth import AuthenticatedActor, AuthenticatedEmployee, get_current_actor, get_current_employee
from app.models.employee_credential import EmployeeCredential
from app.models.employee import Employee
from app.models.staff_access import StaffDepartmentScope, StaffUser
from app.schemas.auth import AuthEmployee, AuthStaff, AuthSubject, ChangePasswordRequest, LoginRequest, LoginResponse
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_LOGIN_RATE_LIMITER = SlidingWindowRateLimiter()


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    normalized_email = payload.email.strip().lower()
    rate_limit_key = _login_rate_limit_key(request=request, normalized_email=normalized_email)
    rate_limit_decision = _LOGIN_RATE_LIMITER.check(
        key=rate_limit_key,
        max_attempts=settings.auth_rate_limit_attempts,
        window_seconds=settings.auth_rate_limit_window_seconds,
    )
    if not rate_limit_decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesión. Intenta nuevamente en unos minutos.",
            headers={"Retry-After": str(rate_limit_decision.retry_after_seconds or 60)},
        )
    if has_staff_access_schema(db):
        staff_user = db.query(StaffUser).filter(func.lower(StaffUser.email) == normalized_email).first()
        if staff_user is not None and staff_user.is_active:
            if not verify_password(payload.password, staff_user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="El correo o la contraseña no son correctos.",
                )
            token = create_access_token(
                {
                    "sub": staff_user.id,
                    "email": staff_user.email,
                    "actor_type": "staff",
                    "is_superadmin": staff_user.is_superadmin,
                },
                settings.auth_secret_key,
                settings.auth_token_ttl_minutes,
            )
            department_ids = [
                int(department_id)
                for (department_id,) in db.query(StaffDepartmentScope.department_id)
                .filter(StaffDepartmentScope.staff_user_id == staff_user.id)
                .all()
            ]
            return _to_staff_login_response(staff_user=staff_user, department_ids=department_ids, settings=settings)

    row = (
        db.query(Employee, EmployeeCredential)
        .join(EmployeeCredential, EmployeeCredential.employee_id == Employee.id)
        .filter(func.lower(Employee.email) == normalized_email)
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El correo o la contraseña no son correctos.",
        )
    employee, credential = row
    if not verify_password(payload.password, credential.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El correo o la contraseña no son correctos.",
        )
    return _to_employee_login_response(
        AuthenticatedEmployee(
            employee=employee,
            must_change_password=credential.must_change_password,
            is_admin=employee.email.strip().lower() == settings.admin_email.strip().lower(),
        ),
        settings,
    )


def reset_auth_rate_limits() -> None:
    _LOGIN_RATE_LIMITER.clear()


def _login_rate_limit_key(*, request: Request, normalized_email: str) -> str:
    client_host = request.client.host if request.client is not None else "unknown"
    return f"{client_host}:{normalized_email}"


@router.get("/me", response_model=AuthSubject)
def get_me(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthSubject:
    if actor.is_staff and actor.staff is not None:
        return AuthSubject(
            actor_type="staff",
            staff=_to_auth_staff(actor.staff, sorted(actor.department_ids or set())),
        )
    authenticated = AuthenticatedEmployee(
        employee=actor.employee,
        must_change_password=actor.must_change_password,
        is_admin=actor.is_admin,
    )
    return AuthSubject(actor_type="employee", employee=_to_auth_employee(authenticated))


@router.post("/change-password", response_model=AuthEmployee | AuthStaff)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    actor: AuthenticatedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthEmployee | AuthStaff:
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes elegir una contraseña diferente")
    if actor.is_staff and actor.staff is not None:
        if not verify_password(payload.current_password, actor.staff.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta")
        actor.staff.password_hash = hash_password(payload.new_password)
        actor.staff.must_change_password = False
        db.add(actor.staff)
        db.commit()
        db.refresh(actor.staff)
        department_ids = [
            int(department_id)
            for (department_id,) in db.query(StaffDepartmentScope.department_id)
            .filter(StaffDepartmentScope.staff_user_id == actor.staff.id)
            .all()
        ]
        updated_staff = _to_auth_staff(actor.staff, department_ids)
        response.headers["X-Modeloasist-Access-Token"] = _build_staff_access_token(
            staff=updated_staff,
            settings=settings,
        )
        return updated_staff

    authenticated = AuthenticatedEmployee(
        employee=actor.employee,
        must_change_password=actor.must_change_password,
        is_admin=actor.is_admin,
    )
    credential = db.query(EmployeeCredential).filter(EmployeeCredential.employee_id == authenticated.employee.id).first()
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credenciales no encontradas")
    if not verify_password(payload.current_password, credential.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta")
    credential.password_hash = hash_password(payload.new_password)
    credential.must_change_password = False
    db.add(credential)
    db.commit()
    db.refresh(credential)
    updated_employee = _to_auth_employee(
        AuthenticatedEmployee(
            employee=authenticated.employee,
            must_change_password=credential.must_change_password,
            is_admin=authenticated.is_admin,
        )
    )
    response.headers["X-Modeloasist-Access-Token"] = _build_employee_access_token(
        employee=updated_employee,
        settings=settings,
    )
    return updated_employee


def _to_employee_login_response(authenticated: AuthenticatedEmployee, settings: Settings) -> LoginResponse:
    employee = _to_auth_employee(authenticated)
    token = _build_employee_access_token(employee=employee, settings=settings)
    return LoginResponse(
        access_token=token,
        actor_type="employee",
        employee=employee,
    )


def _to_staff_login_response(*, staff_user: StaffUser, department_ids: list[int], settings: Settings) -> LoginResponse:
    staff = _to_auth_staff(staff_user, department_ids)
    token = _build_staff_access_token(staff=staff, settings=settings)
    return LoginResponse(
        access_token=token,
        actor_type="staff",
        staff=staff,
    )


def _build_employee_access_token(*, employee: AuthEmployee, settings: Settings) -> str:
    subject = AuthSubject(actor_type="employee", employee=employee)
    return create_access_token(
        {
            "sub": employee.id,
            "email": employee.email,
            "actor_type": "employee",
            "session": subject.model_dump(mode="json"),
        },
        settings.auth_secret_key,
        settings.auth_token_ttl_minutes,
    )


def _build_staff_access_token(*, staff: AuthStaff, settings: Settings) -> str:
    subject = AuthSubject(actor_type="staff", staff=staff)
    return create_access_token(
        {
            "sub": staff.id,
            "email": staff.email,
            "actor_type": "staff",
            "is_superadmin": staff.is_superadmin,
            "session": subject.model_dump(mode="json"),
        },
        settings.auth_secret_key,
        settings.auth_token_ttl_minutes,
    )


def _to_auth_employee(authenticated: AuthenticatedEmployee) -> AuthEmployee:
    employee = authenticated.employee
    return AuthEmployee(
        id=employee.id,
        nombre=employee.nombre,
        email=employee.email,
        departamento=employee.departamento,
        campus=employee.campus,
        must_change_password=authenticated.must_change_password,
        is_admin=authenticated.is_admin,
    )


def _to_auth_staff(staff_user: StaffUser, department_ids: list[int]) -> AuthStaff:
    return AuthStaff(
        id=staff_user.id,
        email=staff_user.email,
        full_name=staff_user.full_name,
        employee_id=staff_user.employee_id,
        must_change_password=staff_user.must_change_password,
        is_superadmin=staff_user.is_superadmin,
        department_ids=department_ids,
    )