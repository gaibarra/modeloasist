"""drop remaining long-form department aliases

Revision ID: 20260508_0007
Revises: 20260508_0006
Create Date: 2026-05-08 13:00:00.000000
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "20260508_0007"
down_revision = "20260508_0006"
branch_labels = None
depends_on = None


_LONG_DEPARTMENT_PATTERN = re.compile(
    r"^escuela\s+modelo\s*[-/]\s*(merida|m[eé]rida|montejo|chetumal|valladolid)\s*[-/]\s*(.+?)\s*$",
    re.IGNORECASE,
)
_GENERIC_PREFIX_PATTERN = re.compile(r"^escuela\s+modelo\s*[-/]\s*(.+?)\s*$", re.IGNORECASE)


def _canonicalize(value: str | None) -> str:
    raw_name = (value or "").strip()
    if not raw_name:
        return ""
    match = _LONG_DEPARTMENT_PATTERN.match(raw_name)
    if match:
        return match.group(2).strip()
    generic_match = _GENERIC_PREFIX_PATTERN.match(raw_name)
    if generic_match:
        return generic_match.group(1).strip()
    return raw_name


def upgrade() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    department_aliases = sa.Table("department_aliases", metadata, autoload_with=connection)

    alias_rows = connection.execute(
        sa.select(
            department_aliases.c.id,
            department_aliases.c.department_id,
            department_aliases.c.alias,
        ).where(sa.func.lower(department_aliases.c.alias).like("escuela modelo%"))
    ).mappings().all()

    for row in alias_rows:
        canonical_alias = _canonicalize(row["alias"])
        if not canonical_alias or canonical_alias == row["alias"]:
            continue
        short_alias_exists = connection.execute(
            sa.select(department_aliases.c.id)
            .where(department_aliases.c.department_id == row["department_id"])
            .where(sa.func.lower(department_aliases.c.alias) == canonical_alias.lower())
        ).first()
        if short_alias_exists:
            connection.execute(
                department_aliases.delete().where(department_aliases.c.id == row["id"])
            )


def downgrade() -> None:
    raise NotImplementedError("Dropping remaining long-form aliases is not reversible.")