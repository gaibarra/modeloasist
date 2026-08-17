"""add duplicate breakdown to attendance import batches

Revision ID: 20260506_0003
Revises: 20260506_0002
Create Date: 2026-05-06 18:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_0003"
down_revision = "20260506_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendance_import_batches", sa.Column("duplicate_breakdown", sa.JSON(), nullable=True))
    op.execute("update attendance_import_batches set duplicate_breakdown = '[]' where duplicate_breakdown is null")
    op.alter_column("attendance_import_batches", "duplicate_breakdown", nullable=False)


def downgrade() -> None:
    op.drop_column("attendance_import_batches", "duplicate_breakdown")