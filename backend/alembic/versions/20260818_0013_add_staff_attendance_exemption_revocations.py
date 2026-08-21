"""add revocation audit fields for personal attendance exemptions

Revision ID: 20260818_0013
Revises: 20260818_0012
"""
from alembic import op
import sqlalchemy as sa

revision = "20260818_0013"
down_revision = "20260818_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("staff_attendance_exemptions", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    op.add_column("staff_attendance_exemptions", sa.Column("revoked_by_staff_user_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_staff_attendance_exemption_revoked_by",
        "staff_attendance_exemptions",
        "staff_users",
        ["revoked_by_staff_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_staff_attendance_exemption_revoked_by", "staff_attendance_exemptions", type_="foreignkey")
    op.drop_column("staff_attendance_exemptions", "revoked_by_staff_user_id")
    op.drop_column("staff_attendance_exemptions", "revoked_at")
