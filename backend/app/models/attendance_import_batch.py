"""ORM model for attendance Excel upload batches."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AttendanceImportBatch(Base):
    __tablename__ = "attendance_import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    uploaded_by_staff_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_breakdown: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    auto_created_employees: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)

    uploaded_by = relationship("StaffUser", back_populates="attendance_import_batches")