"""add personal attendance exemptions

Revision ID: 20260818_0012
Revises: 20260817_0011
"""
from alembic import op
import sqlalchemy as sa

revision = "20260818_0012"
down_revision = "20260817_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_attendance_exemptions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("department_id", sa.BigInteger(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("exempt_entry", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("exempt_exit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("granted_by_staff_user_id", sa.BigInteger(), sa.ForeignKey("staff_users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "target_date", name="uq_staff_attendance_exemption_day"),
    )
    op.create_index("ix_staff_attendance_exemption_employee_date", "staff_attendance_exemptions", ["employee_id", "target_date"])


def downgrade() -> None:
    op.drop_index("ix_staff_attendance_exemption_employee_date", table_name="staff_attendance_exemptions")
    op.drop_table("staff_attendance_exemptions")
