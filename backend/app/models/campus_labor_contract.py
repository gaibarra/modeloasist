"""Versioned campus-specific contracts; legacy contracts remain untouched."""
from sqlalchemy import Column, Integer, BigInteger, String, Text, Date, DateTime, Boolean, ForeignKey, CheckConstraint, Index, func, text
from app.db.base import Base


class CampusLaborContract(Base):
    __tablename__ = 'campus_labor_contracts'
    __table_args__ = (
        CheckConstraint('weekly_minutes IS NULL OR (weekly_minutes >= 0 AND weekly_minutes <= 10080)', name='ck_campus_contract_minutes'),
        CheckConstraint('valid_from <= valid_until', name='ck_campus_contract_dates'),
        Index('uq_campus_contract_active_period', 'employee_id', 'campus_code', 'valid_from', 'valid_until', unique=True,
              postgresql_where=text('active'), sqlite_where=text('active = 1')),
    )
    id = Column(Integer, primary_key=True)
    employee_id = Column(BigInteger, ForeignKey('employees.id'), nullable=False, index=True)
    campus_code = Column(String(8), nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=False)
    weekly_minutes = Column(Integer, nullable=True)  # NULL is pending, never zero.
    job_title = Column(Text, nullable=False, default='')
    department_code = Column(Text, nullable=False, default='')
    department_name = Column(Text, nullable=False, default='')
    source_employee_key = Column(Text, nullable=False, default='')
    source_sheet = Column(Text, nullable=False)
    source_row = Column(Integer, nullable=False)
    import_id = Column(Integer, ForeignKey('labor_contract_imports.id'), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
