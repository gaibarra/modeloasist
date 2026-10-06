"""Keep semester file imports and their per-person reconciliation audit."""
from alembic import op
import sqlalchemy as sa

revision = "20260914_0014"
down_revision = "20260818_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "staff_schedule_file_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("academic_year", sa.Integer(), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("audit", sa.JSON(), nullable=False),
        sa.UniqueConstraint("source_sha256", "academic_year", "semester", name="uq_schedule_file_import"),
    )


def downgrade():
    op.drop_table("staff_schedule_file_imports")
