"""normalize remaining escuela modelo department prefixes

Revision ID: 20260508_0005
Revises: 20260508_0004
Create Date: 2026-05-08 12:20:00.000000
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "20260508_0005"
down_revision = "20260508_0004"
branch_labels = None
depends_on = None


_GENERIC_PREFIX_PATTERN = re.compile(r"^escuela\s+modelo\s*[-/]\s*(.+?)\s*$", re.IGNORECASE)


def _canonicalize(value: str | None) -> str:
    raw_name = (value or "").strip()
    if not raw_name:
        return ""
    match = _GENERIC_PREFIX_PATTERN.match(raw_name)
    if match:
        return match.group(1).strip()
    return raw_name


def upgrade() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    employees = sa.Table("employees", metadata, autoload_with=connection)
    attendance_events = sa.Table("attendance_events", metadata, autoload_with=connection)
    departments = sa.Table("departments", metadata, autoload_with=connection)
    department_aliases = sa.Table("department_aliases", metadata, autoload_with=connection)

    employee_rows = connection.execute(
        sa.select(employees.c.id, employees.c.departamento).where(sa.func.lower(employees.c.departamento).like("escuela modelo%"))
    ).mappings().all()
    for row in employee_rows:
        canonical_name = _canonicalize(row["departamento"])
        if canonical_name and canonical_name != row["departamento"]:
            connection.execute(
                employees.update().where(employees.c.id == row["id"]).values(departamento=canonical_name)
            )

    attendance_rows = connection.execute(
        sa.select(attendance_events.c.id, attendance_events.c.departamento_raw).where(sa.func.lower(attendance_events.c.departamento_raw).like("escuela modelo%"))
    ).mappings().all()
    for row in attendance_rows:
        canonical_name = _canonicalize(row["departamento_raw"])
        if canonical_name and canonical_name != row["departamento_raw"]:
            connection.execute(
                attendance_events.update().where(attendance_events.c.id == row["id"]).values(departamento_raw=canonical_name)
            )

    department_rows = connection.execute(
        sa.select(departments.c.id, departments.c.name).where(sa.func.lower(departments.c.name).like("escuela modelo%"))
    ).mappings().all()
    for row in department_rows:
        canonical_name = _canonicalize(row["name"])
        if not canonical_name or canonical_name == row["name"]:
            continue
        connection.execute(
            departments.update().where(departments.c.id == row["id"]).values(name=canonical_name)
        )
        existing_alias = connection.execute(
            sa.select(department_aliases.c.id)
            .where(department_aliases.c.department_id == row["id"])
            .where(sa.func.lower(department_aliases.c.alias) == canonical_name.lower())
        ).first()
        if not existing_alias:
            connection.execute(
                department_aliases.insert().values(
                    department_id=row["id"],
                    alias=canonical_name,
                    source="normalization",
                )
            )


def downgrade() -> None:
    raise NotImplementedError("This department prefix normalization migration is not reversible.")