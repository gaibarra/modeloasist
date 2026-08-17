"""add attendance import batches

Revision ID: 20260506_0002
Revises: 20260320_0001
Create Date: 2026-05-06 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260506_0002"
down_revision = "20260320_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_import_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("uploaded_by_staff_user_id", sa.BigInteger(), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False),
        sa.Column("skipped_duplicates", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("auto_created_employees", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_staff_user_id"], ["staff_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_attendance_import_batches_uploaded_by_staff_user_id"),
        "attendance_import_batches",
        ["uploaded_by_staff_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_attendance_import_batches_uploaded_by_staff_user_id"),
        table_name="attendance_import_batches",
    )
    op.drop_table("attendance_import_batches")