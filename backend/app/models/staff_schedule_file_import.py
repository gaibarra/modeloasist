"""Immutable receipt: identity matches, source rows and before/after schedules."""
from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, UniqueConstraint, func
from app.db.base import Base


class StaffScheduleFileImport(Base):
    __tablename__ = "staff_schedule_file_imports"
    __table_args__ = (UniqueConstraint("source_sha256", "academic_year", "semester", name="uq_schedule_file_import"),)
    id = Column(Integer, primary_key=True)
    source_sha256 = Column(String(64), nullable=False)
    source_name = Column(Text, nullable=False)
    academic_year = Column(Integer, nullable=False)
    semester = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audit = Column(JSON, nullable=False)
