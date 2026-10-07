"""Versioned weekly labor contracts and audited imports."""
from alembic import op
import sqlalchemy as sa

revision = "20261007_0015"
down_revision = "20260914_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("labor_contract_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_sha256", sa.String(64), nullable=False, index=True),
        sa.Column("request_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("staff_user_id", sa.BigInteger(), sa.ForeignKey("staff_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("audit", sa.JSON(), nullable=False),
        sa.Column("reverted_at", sa.DateTime(timezone=True)),
        sa.Column("reverted_by", sa.BigInteger(), sa.ForeignKey("staff_users.id")))
    op.create_table("labor_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.BigInteger(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("weekly_minutes", sa.Integer(), nullable=False),
        sa.Column("source_sheet", sa.Text(), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), sa.ForeignKey("labor_contract_imports.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("weekly_minutes >= 0 AND weekly_minutes <= 10080", name="ck_labor_contract_minutes"),
        sa.CheckConstraint("valid_from <= valid_until", name="ck_labor_contract_dates"))


def downgrade():
    op.drop_table("labor_contracts")
    op.drop_table("labor_contract_imports")
