"""add staff-managed semester schedules

Revision ID: 20260817_0008
Revises: 20260508_0007
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260817_0008"
down_revision = "20260508_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_semester_schedules",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("employee_id", sa.BigInteger(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year", sa.Integer(), nullable=False),
        sa.Column("semester", sa.SmallInteger(), nullable=False),
        sa.Column("updated_by_staff_user_id", sa.BigInteger(), sa.ForeignKey("staff_users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "academic_year", "semester", name="uq_staff_semester_schedule_period"),
    )
    op.create_index("ix_staff_semester_schedules_employee_id", "staff_semester_schedules", ["employee_id"])
    op.create_table(
        "staff_semester_schedule_intervals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("schedule_id", sa.BigInteger(), sa.ForeignKey("staff_semester_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start", sa.Time(), nullable=False),
        sa.Column("end", sa.Time(), nullable=False),
    )
    op.create_index("ix_staff_semester_schedule_intervals_schedule_id", "staff_semester_schedule_intervals", ["schedule_id"])
    # Preserve the schedules already loaded from the institutional source as the
    # historical reference for the first semester of the 2026 reporting year.
    op.execute(
        """
        INSERT INTO staff_semester_schedules (employee_id, academic_year, semester)
        SELECT DISTINCT employee_id, 2026, 1
        FROM schedules
        WHERE employee_id IS NOT NULL AND dia_letra IS NOT NULL
        ON CONFLICT (employee_id, academic_year, semester) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO staff_semester_schedule_intervals (schedule_id, weekday, start, "end")
        SELECT semester_schedule.id,
               CASE schedules.dia_letra
                   WHEN 'Lunes' THEN 0 WHEN 'Martes' THEN 1 WHEN 'Miércoles' THEN 2
                   WHEN 'Jueves' THEN 3 WHEN 'Viernes' THEN 4 WHEN 'Sábado' THEN 5
                   WHEN 'Domingo' THEN 6
               END,
               schedules.inicio,
               schedules.fin
        FROM schedules
        JOIN staff_semester_schedules AS semester_schedule
          ON semester_schedule.employee_id = schedules.employee_id
         AND semester_schedule.academic_year = 2026
         AND semester_schedule.semester = 1
        WHERE schedules.employee_id IS NOT NULL
          AND schedules.dia_letra IN ('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo')
        """
    )


def downgrade() -> None:
    op.drop_table("staff_semester_schedule_intervals")
    op.drop_table("staff_semester_schedules")
