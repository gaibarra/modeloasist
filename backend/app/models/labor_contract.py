"""Versioned labor hours and reversible import receipts; never biometric data."""
from sqlalchemy import Column, Integer, BigInteger, String, Text, Date, DateTime, Boolean, JSON, ForeignKey, UniqueConstraint, CheckConstraint, func
from app.db.base import Base


class LaborContractImport(Base):
    __tablename__ = "labor_contract_imports"
    id = Column(Integer, primary_key=True)
    source_sha256 = Column(String(64), nullable=False, index=True)
    request_sha256 = Column(String(64), nullable=False, unique=True)
    source_name = Column(Text, nullable=False)
    staff_user_id = Column(BigInteger, ForeignKey("staff_users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit = Column(JSON, nullable=False)
    reverted_at = Column(DateTime(timezone=True))
    reverted_by = Column(BigInteger, ForeignKey("staff_users.id"))


class LaborContract(Base):
    __tablename__ = "labor_contracts"
    __table_args__ = (CheckConstraint("weekly_minutes >= 0 AND weekly_minutes <= 10080", name="ck_labor_contract_minutes"),
                      CheckConstraint("valid_from <= valid_until", name="ck_labor_contract_dates"))
    id = Column(Integer, primary_key=True)
    employee_id = Column(BigInteger, ForeignKey("employees.id"), nullable=False, index=True)
    valid_from = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=False)
    weekly_minutes = Column(Integer, nullable=False)
    source_sheet = Column(Text, nullable=False)
    source_row = Column(Integer, nullable=False)
    import_id = Column(Integer, ForeignKey("labor_contract_imports.id"), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
