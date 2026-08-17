"""normalize long department names to canonical short names

Revision ID: 20260508_0004
Revises: 20260506_0003
Create Date: 2026-05-08 12:00:00.000000
"""

from __future__ import annotations

from collections import defaultdict
import re

from alembic import op
import sqlalchemy as sa


revision = "20260508_0004"
down_revision = "20260506_0003"
branch_labels = None
depends_on = None


_LONG_DEPARTMENT_PATTERN = re.compile(
    r"^escuela\s+modelo\s*[-/]\s*(merida|m[eé]rida|montejo|chetumal|valladolid)\s*[-/]\s*(.+?)\s*$",
    re.IGNORECASE,
)
_GENERIC_PREFIX_PATTERN = re.compile(r"^escuela\s+modelo\s*[-/]\s*(.+?)\s*$", re.IGNORECASE)
_CAMPUS_DISPLAY_NAMES = {
    "merida": "Mérida",
    "mérida": "Mérida",
    "montejo": "Montejo",
    "chetumal": "Chetumal",
    "valladolid": "Valladolid",
}


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _canonicalize_department(value: str | None) -> tuple[str, str, str | None]:
    raw_name = (value or "").strip()
    if not raw_name:
        return "", "", None
    match = _LONG_DEPARTMENT_PATTERN.match(raw_name)
    if match:
        campus = _CAMPUS_DISPLAY_NAMES.get(match.group(1).strip().lower())
        canonical_name = match.group(2).strip()
        return raw_name, canonical_name, campus
    generic_match = _GENERIC_PREFIX_PATTERN.match(raw_name)
    if generic_match:
        canonical_name = generic_match.group(1).strip()
        return raw_name, canonical_name, None
    return raw_name, raw_name, None


def _choose_survivor(rows: list[dict[str, object]], canonical_name: str) -> dict[str, object]:
    exact_match = [row for row in rows if (row.get("name") or "").strip() == canonical_name]
    pool = exact_match or rows
    return sorted(pool, key=lambda row: int(row["id"]))[0]


def _ensure_alias(
    connection,
    department_aliases,
    *,
    department_id: int,
    alias_value: str,
    source: str = "normalization",
) -> None:
    alias_value = (alias_value or "").strip()
    if not alias_value:
        return
    existing = connection.execute(
        sa.select(department_aliases.c.id, department_aliases.c.department_id, department_aliases.c.alias)
        .where(sa.func.lower(department_aliases.c.alias) == _normalize(alias_value))
    ).mappings().first()
    if existing:
        if int(existing["department_id"]) != department_id:
            connection.execute(
                department_aliases.update()
                .where(department_aliases.c.id == existing["id"])
                .values(department_id=department_id)
            )
        return
    connection.execute(
        department_aliases.insert().values(
            department_id=department_id,
            alias=alias_value,
            source=source,
        )
    )


def _move_relationship_rows(connection, table, old_department_id: int, new_department_id: int, key_column: str) -> None:
    rows = connection.execute(
        sa.select(getattr(table.c, key_column)).where(table.c.department_id == old_department_id)
    ).all()
    for (row_key,) in rows:
        exists = connection.execute(
            sa.select(table.c.department_id)
            .where(getattr(table.c, key_column) == row_key)
            .where(table.c.department_id == new_department_id)
        ).first()
        if exists:
            connection.execute(
                table.delete()
                .where(getattr(table.c, key_column) == row_key)
                .where(table.c.department_id == old_department_id)
            )
            continue
        connection.execute(
            table.update()
            .where(getattr(table.c, key_column) == row_key)
            .where(table.c.department_id == old_department_id)
            .values(department_id=new_department_id)
        )


def upgrade() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    departments = sa.Table("departments", metadata, autoload_with=connection)
    department_aliases = sa.Table("department_aliases", metadata, autoload_with=connection)
    employee_departments = sa.Table("employee_departments", metadata, autoload_with=connection)
    staff_department_scopes = sa.Table("staff_department_scopes", metadata, autoload_with=connection)
    employees = sa.Table("employees", metadata, autoload_with=connection)
    attendance_events = sa.Table("attendance_events", metadata, autoload_with=connection)

    employee_rows = connection.execute(sa.select(employees.c.id, employees.c.departamento, employees.c.campus)).mappings().all()
    for employee in employee_rows:
        raw_name, canonical_name, campus = _canonicalize_department(employee["departamento"])
        values: dict[str, object] = {}
        if canonical_name and employee["departamento"] != canonical_name:
            values["departamento"] = canonical_name
        if campus and employee["campus"] != campus:
            values["campus"] = campus
        if values:
            connection.execute(employees.update().where(employees.c.id == employee["id"]).values(**values))

    attendance_rows = connection.execute(sa.select(attendance_events.c.id, attendance_events.c.departamento_raw)).mappings().all()
    for attendance in attendance_rows:
        _, canonical_name, _ = _canonicalize_department(attendance["departamento_raw"])
        if canonical_name and attendance["departamento_raw"] != canonical_name:
            connection.execute(
                attendance_events.update()
                .where(attendance_events.c.id == attendance["id"])
                .values(departamento_raw=canonical_name)
            )

    department_rows = [dict(row) for row in connection.execute(sa.select(departments)).mappings().all()]
    if not department_rows:
        return

    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in department_rows:
        _, canonical_name, _ = _canonicalize_department(row["name"])
        group_key = canonical_name or (row["name"] or "").strip()
        if group_key:
            groups[group_key].append(row)

    alias_rows = connection.execute(sa.select(department_aliases)).mappings().all()
    aliases_by_department: dict[int, list[dict[str, object]]] = defaultdict(list)
    for alias in alias_rows:
        aliases_by_department[int(alias["department_id"])].append(dict(alias))

    for canonical_name, rows in groups.items():
        survivor = _choose_survivor(rows, canonical_name)
        survivor_id = int(survivor["id"])
        campuses = []
        alias_values = {canonical_name}
        for row in rows:
            row_raw_name, _, row_campus = _canonicalize_department(row["name"])
            if row_raw_name:
                alias_values.add(row_raw_name)
            if row_campus:
                campuses.append(row_campus)
            if row.get("campus"):
                campuses.append(row["campus"])
            for alias in aliases_by_department.get(int(row["id"]), []):
                alias_values.add((alias.get("alias") or "").strip())
                _, _, alias_campus = _canonicalize_department(alias.get("alias"))
                if alias_campus:
                    campuses.append(alias_campus)

        canonical_campus = next((campus for campus in campuses if campus), None)
        values: dict[str, object] = {}
        if survivor.get("name") != canonical_name:
            values["name"] = canonical_name
        if canonical_campus and survivor.get("campus") != canonical_campus:
            values["campus"] = canonical_campus
        if values:
            connection.execute(departments.update().where(departments.c.id == survivor_id).values(**values))

        for alias_value in sorted(alias_values):
            _ensure_alias(connection, department_aliases, department_id=survivor_id, alias_value=alias_value)

        duplicate_ids = [int(row["id"]) for row in rows if int(row["id"]) != survivor_id]
        for duplicate_id in duplicate_ids:
            _move_relationship_rows(connection, employee_departments, duplicate_id, survivor_id, "employee_id")
            _move_relationship_rows(connection, staff_department_scopes, duplicate_id, survivor_id, "staff_user_id")
            connection.execute(department_aliases.delete().where(department_aliases.c.department_id == duplicate_id))
            connection.execute(departments.delete().where(departments.c.id == duplicate_id))


def downgrade() -> None:
    raise NotImplementedError("This department normalization migration is not reversible.")