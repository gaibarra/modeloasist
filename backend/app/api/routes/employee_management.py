"""Owner-only collaborator directory and mutations."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.db.session import get_db
from app.db.base import Base
from app.dependencies.auth import AuthenticatedActor, get_current_actor
from app.models.employee import Employee
from app.models.staff_access import Department, EmployeeDepartment, StaffUser

OWNER = "gaibarra@hotmail.com"


def require_owner(actor: AuthenticatedActor = Depends(get_current_actor)):
    subject = actor.staff if actor.is_staff else actor.employee
    if subject is None or subject.email.strip().lower() != OWNER:
        raise HTTPException(403, "Acceso exclusivo para gaibarra@hotmail.com")
    return actor


router = APIRouter(
    prefix="/employees/manage", tags=["employee management"], dependencies=[Depends(require_owner)]
)


class EmployeeWrite(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    email: EmailStr
    department_ids: list[int] = Field(min_length=1, max_length=50)
    primary_department_id: int
    external_employee_id: int | None = Field(default=None, ge=1, le=9223372036854775807)
    division: str | None = Field(default=None, max_length=128)

    @field_validator("nombre", "division", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


def serialize(e):
    return dict(
        id=e.id,
        nombre=e.nombre,
        email=e.email,
        campus=e.campus,
        departamento=e.departamento,
        division=e.division,
        external_employee_id=e.external_employee_id,
        department_ids=[x.department_id for x in e.department_links],
        primary_department_id=next(
            (x.department_id for x in e.department_links if x.is_primary), None
        ),
    )


@router.get("/departments")
def departments(db: Session = Depends(get_db)):
    return [
        dict(id=d.id, name=d.name, campus=d.campus, active=d.active)
        for d in db.scalars(select(Department).order_by(Department.name))
    ]


@router.get("")
def directory(
    q: str = Query("", max_length=200),
    department_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    filters = []
    if q.strip():
        pattern = (
            "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        filters.append(
            or_(
                Employee.nombre.ilike(pattern, escape="\\"),
                Employee.email.ilike(pattern, escape="\\"),
            )
        )
    if department_id is not None:
        filters.append(
            Employee.id.in_(
                select(EmployeeDepartment.employee_id).where(
                    EmployeeDepartment.department_id == department_id
                )
            )
        )
    rows = db.scalars(
        select(Employee)
        .options(selectinload(Employee.department_links))
        .where(*filters)
        .order_by(Employee.nombre, Employee.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return dict(
        items=[serialize(e) for e in rows],
        total=db.scalar(select(func.count()).select_from(Employee).where(*filters)),
        registered=db.scalar(select(func.count()).select_from(Employee)),
    )


def get_employee(db, employee_id):
    e = db.scalar(
        select(Employee)
        .options(selectinload(Employee.department_links))
        .where(Employee.id == employee_id)
    )
    if not e:
        raise HTTPException(404, "Colaborador no encontrado")
    return e


@router.get("/{employee_id}")
def detail(employee_id: int, db: Session = Depends(get_db)):
    return serialize(get_employee(db, employee_id))


def save(db, e, payload):
    ids = set(payload.department_ids)
    depts = {d.id: d for d in db.scalars(select(Department).where(Department.id.in_(ids)))}
    if set(depts) != ids or payload.primary_department_id not in ids:
        raise HTTPException(422, "Selecciona departamentos válidos y uno principal")
    email = str(payload.email).lower()
    if (e.email or "").strip().lower() == OWNER and email != OWNER:
        raise HTTPException(409, "El correo de la cuenta administradora está protegido")
    if db.scalar(
        select(Employee.id).where(func.lower(Employee.email) == email, Employee.id != e.id)
    ):
        raise HTTPException(409, "Este correo ya pertenece a otro colaborador")
    if payload.external_employee_id is not None and db.scalar(
        select(Employee.id).where(
            Employee.external_employee_id == payload.external_employee_id, Employee.id != e.id
        )
    ):
        raise HTTPException(409, "El identificador del checador ya está registrado")
    primary = depts[payload.primary_department_id]
    e.nombre, e.email = payload.nombre, email
    e.departamento, e.campus = primary.name, primary.campus
    e.division, e.external_employee_id = payload.division or None, payload.external_employee_id
    existing = {x.department_id: x for x in e.department_links}
    for x in list(e.department_links):
        if x.department_id not in ids:
            e.department_links.remove(x)
    for did in ids:
        if did in existing:
            existing[did].is_primary = did == primary.id
        else:
            e.department_links.append(
                EmployeeDepartment(department_id=did, is_primary=did == primary.id)
            )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "El registro entra en conflicto con otro colaborador; revisa correo e identificador",
        )
    return serialize(e)


@router.post("", status_code=201)
def create(payload: EmployeeWrite, db: Session = Depends(get_db)):
    # Imported employee IDs are allocated explicitly; serialize local allocation.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(text("LOCK TABLE employees IN SHARE ROW EXCLUSIVE MODE"))
    e = Employee(id=(db.scalar(select(func.max(Employee.id))) or 0) + 1)
    db.add(e)
    return save(db, e, payload)


@router.put("/{employee_id}")
def update(employee_id: int, payload: EmployeeWrite, db: Session = Depends(get_db)):
    return save(db, get_employee(db, employee_id), payload)


@router.delete("/{employee_id}", status_code=204)
def remove(employee_id: int, db: Session = Depends(get_db)):
    e = get_employee(db, employee_id)
    if e.email.strip().lower() == OWNER or db.scalar(
        select(StaffUser.id).where(StaffUser.employee_id == e.id)
    ):
        raise HTTPException(
            409, "No se puede eliminar una cuenta vinculada al acceso administrativo o staff"
        )
    # Keep attendance, contracts, schedules and exception history intact.
    allowed = {"employee_departments", "employee_credentials"}
    for table in Base.metadata.sorted_tables:
        if table.name in allowed:
            continue
        for fk in table.foreign_keys:
            if fk.target_fullname == "employees.id" and db.scalar(
                select(func.count()).select_from(table).where(fk.parent == employee_id)
            ):
                raise HTTPException(
                    409,
                    "Este colaborador tiene historial, horarios o contratos asociados. Su eliminación está protegida.",
                )
    try:
        for name in allowed:
            table = Base.metadata.tables.get(name)
            if table is not None:
                db.execute(delete(table).where(table.c.employee_id == employee_id))
        db.execute(delete(Employee).where(Employee.id == employee_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Existen registros asociados que impiden eliminar al colaborador")
    return Response(status_code=204)
