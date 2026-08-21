"""Authorized work on official rest days."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_PRIMARY_KEY = BigInteger().with_variant(Integer, "sqlite")


class StaffHolidayWorkAssignment(Base):
    __tablename__ = "staff_holiday_work_assignments"

    id: Mapped[int] = mapped_column(_PRIMARY_KEY, primary_key=True)
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    holiday_name: Mapped[str] = mapped_column(String(255), nullable=False)
    assigned_by_staff_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
