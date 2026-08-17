"""Manual semester schedules maintained by staff users."""
from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import BigInteger, ForeignKey, Integer, SmallInteger, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class StaffSemesterSchedule(Base):
    __tablename__ = "staff_semester_schedules"
    __table_args__ = (
        UniqueConstraint("employee_id", "academic_year", "semester", name="uq_staff_semester_schedule_period"),
    )

    id: Mapped[int] = mapped_column(_PK, primary_key=True)
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    updated_by_staff_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    intervals = relationship("StaffSemesterScheduleInterval", back_populates="schedule", cascade="all, delete-orphan", order_by="StaffSemesterScheduleInterval.weekday, StaffSemesterScheduleInterval.start")


class StaffSemesterScheduleInterval(Base):
    __tablename__ = "staff_semester_schedule_intervals"

    id: Mapped[int] = mapped_column(_PK, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(_PK, ForeignKey("staff_semester_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start: Mapped[time] = mapped_column(Time, nullable=False)
    end: Mapped[time] = mapped_column(Time, nullable=False)

    schedule = relationship("StaffSemesterSchedule", back_populates="intervals")
