"""Personal staff-authorized exemptions for attendance marks."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_PRIMARY_KEY = BigInteger().with_variant(Integer, "sqlite")


class StaffAttendanceExemption(Base):
    __tablename__ = "staff_attendance_exemptions"

    id: Mapped[int] = mapped_column(_PRIMARY_KEY, primary_key=True)
    department_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("departments.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    exempt_entry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exempt_exit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_by_staff_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by_staff_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff_users.id", ondelete="SET NULL"),
        nullable=True,
    )
