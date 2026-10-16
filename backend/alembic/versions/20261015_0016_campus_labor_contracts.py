"""Add campus contracts without changing legacy contracts or other campuses."""
from alembic import op
import sqlalchemy as sa

revision = '20261015_0016'
down_revision = '20261007_0015'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('campus_labor_contracts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_id', sa.BigInteger(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('campus_code', sa.String(8), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=False),
        sa.Column('weekly_minutes', sa.Integer(), nullable=True),
        sa.Column('job_title', sa.Text(), nullable=False),
        sa.Column('department_code', sa.Text(), nullable=False),
        sa.Column('department_name', sa.Text(), nullable=False),
        sa.Column('source_employee_key', sa.Text(), nullable=False),
        sa.Column('source_sheet', sa.Text(), nullable=False),
        sa.Column('source_row', sa.Integer(), nullable=False),
        sa.Column('import_id', sa.Integer(), sa.ForeignKey('labor_contract_imports.id'), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('weekly_minutes IS NULL OR (weekly_minutes >= 0 AND weekly_minutes <= 10080)', name='ck_campus_contract_minutes'),
        sa.CheckConstraint('valid_from <= valid_until', name='ck_campus_contract_dates'))
    op.create_index('ix_campus_labor_contracts_employee_id', 'campus_labor_contracts', ['employee_id'])
    op.create_index('uq_campus_contract_active_period', 'campus_labor_contracts', ['employee_id','campus_code','valid_from','valid_until'], unique=True,
                    postgresql_where=sa.text('active'), sqlite_where=sa.text('active = 1'))


def downgrade():
    op.drop_table('campus_labor_contracts')
