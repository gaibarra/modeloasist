"""add staff official-holiday work assignments

Revision ID: 20260817_0011
Revises: 20260817_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20260817_0011"
down_revision = "20260817_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_holiday_work_assignments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.BigInteger(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("holiday_name", sa.String(255), nullable=False),
        sa.Column("assigned_by_staff_user_id", sa.BigInteger(), sa.ForeignKey("staff_users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "holiday_date", name="uq_staff_holiday_work_assignment"),
    )
    op.create_index("ix_staff_holiday_work_assignment_employee_date", "staff_holiday_work_assignments", ["employee_id", "holiday_date"])


def downgrade() -> None:
    op.drop_index("ix_staff_holiday_work_assignment_employee_date", table_name="staff_holiday_work_assignments")
    op.drop_table("staff_holiday_work_assignments")
