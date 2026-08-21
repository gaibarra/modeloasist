"""add immutable audit rows for bulk schedule changes

Revision ID: 20260817_0010
Revises: 20260817_0009
"""
from alembic import op
import sqlalchemy as sa

revision = "20260817_0010"
down_revision = "20260817_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_schedule_bulk_operation_changes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bulk_operation_id", sa.BigInteger(), sa.ForeignKey("staff_schedule_bulk_operations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("previous_intervals", sa.JSON(), nullable=False),
        sa.Column("applied_intervals", sa.JSON(), nullable=False),
    )
    op.create_index("ix_staff_schedule_bulk_change_operation", "staff_schedule_bulk_operation_changes", ["bulk_operation_id"])
    op.create_index("ix_staff_schedule_bulk_change_employee", "staff_schedule_bulk_operation_changes", ["employee_id"])
    op.create_index("ix_staff_schedule_bulk_change_date", "staff_schedule_bulk_operation_changes", ["target_date"])


def downgrade() -> None:
    op.drop_index("ix_staff_schedule_bulk_change_date", table_name="staff_schedule_bulk_operation_changes")
    op.drop_index("ix_staff_schedule_bulk_change_employee", table_name="staff_schedule_bulk_operation_changes")
    op.drop_index("ix_staff_schedule_bulk_change_operation", table_name="staff_schedule_bulk_operation_changes")
    op.drop_table("staff_schedule_bulk_operation_changes")
