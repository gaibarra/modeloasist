"""add date schedule overrides

Revision ID: 20260817_0009
Revises: 20260817_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20260817_0009"
down_revision = "20260817_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_schedule_bulk_operations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("staff_user_id", sa.BigInteger(), sa.ForeignKey("staff_users.id"), nullable=False),
        sa.Column("department_id", sa.BigInteger(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("instruction", sa.String(1000), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "staff_schedule_date_overrides",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.BigInteger(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("bulk_operation_id", sa.BigInteger(), sa.ForeignKey("staff_schedule_bulk_operations.id", ondelete="SET NULL")),
    )
    op.create_index("ix_staff_schedule_date_override_employee_date", "staff_schedule_date_overrides", ["employee_id", "target_date"], unique=True)
    op.create_table(
        "staff_schedule_date_override_intervals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("override_id", sa.BigInteger(), sa.ForeignKey("staff_schedule_date_overrides.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("start", sa.Time(), nullable=False),
        sa.Column("end", sa.Time(), nullable=False),
    )
    op.create_index("ix_staff_schedule_date_override_interval_override", "staff_schedule_date_override_intervals", ["override_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_schedule_date_override_interval_override", table_name="staff_schedule_date_override_intervals")
    op.drop_table("staff_schedule_date_override_intervals")
    op.drop_table("staff_schedule_date_overrides")
    op.drop_table("staff_schedule_bulk_operations")
