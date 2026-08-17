"""add staff access tables

Revision ID: 20260320_0001
Revises: None
Create Date: 2026-03-20 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("campus", sa.String(length=128), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_departments_id"), "departments", ["id"], unique=False)
    op.create_index(op.f("ix_departments_code"), "departments", ["code"], unique=True)
    op.create_index(op.f("ix_departments_campus"), "departments", ["campus"], unique=False)

    op.create_table(
        "department_aliases",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("alias", name="uq_department_aliases_alias"),
    )
    op.create_index(op.f("ix_department_aliases_id"), "department_aliases", ["id"], unique=False)
    op.create_index(op.f("ix_department_aliases_department_id"), "department_aliases", ["department_id"], unique=False)

    op.create_table(
        "staff_users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("employee_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("employee_id"),
    )
    op.create_index(op.f("ix_staff_users_id"), "staff_users", ["id"], unique=False)
    op.create_index(op.f("ix_staff_users_email"), "staff_users", ["email"], unique=True)

    op.create_table(
        "employee_departments",
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("employee_id", "department_id"),
    )

    op.create_table(
        "staff_department_scopes",
        sa.Column("staff_user_id", sa.BigInteger(), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_user_id"], ["staff_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("staff_user_id", "department_id"),
    )



def downgrade() -> None:
    op.drop_table("staff_department_scopes")
    op.drop_table("employee_departments")
    op.drop_index(op.f("ix_staff_users_email"), table_name="staff_users")
    op.drop_index(op.f("ix_staff_users_id"), table_name="staff_users")
    op.drop_table("staff_users")
    op.drop_index(op.f("ix_department_aliases_department_id"), table_name="department_aliases")
    op.drop_index(op.f("ix_department_aliases_id"), table_name="department_aliases")
    op.drop_table("department_aliases")
    op.drop_index(op.f("ix_departments_campus"), table_name="departments")
    op.drop_index(op.f("ix_departments_code"), table_name="departments")
    op.drop_index(op.f("ix_departments_id"), table_name="departments")
    op.drop_table("departments")
