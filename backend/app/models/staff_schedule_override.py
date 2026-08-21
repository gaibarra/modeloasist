"""Date-specific staff schedule overrides created by bulk operations."""
from datetime import date, datetime, time
from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, JSON, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

_PRIMARY_KEY = BigInteger().with_variant(Integer, "sqlite")

class StaffScheduleBulkOperation(Base):
    __tablename__ = "staff_schedule_bulk_operations"
    id: Mapped[int] = mapped_column(_PRIMARY_KEY, primary_key=True)
    staff_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("staff_users.id"), nullable=False)
    department_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("departments.id"), nullable=False)
    instruction: Mapped[str] = mapped_column(String(1000), nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class StaffScheduleDateOverride(Base):
    __tablename__ = "staff_schedule_date_overrides"
    id: Mapped[int] = mapped_column(_PRIMARY_KEY, primary_key=True)
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bulk_operation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("staff_schedule_bulk_operations.id", ondelete="SET NULL"), nullable=True)
    intervals: Mapped[list["StaffScheduleDateOverrideInterval"]] = relationship(
        cascade="all, delete-orphan",
        order_by="StaffScheduleDateOverrideInterval.position",
    )


class StaffScheduleDateOverrideInterval(Base):
    __tablename__ = "staff_schedule_date_override_intervals"

    id: Mapped[int] = mapped_column(_PRIMARY_KEY, primary_key=True)
    override_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff_schedule_date_overrides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    start: Mapped[time] = mapped_column(Time, nullable=False)
    end: Mapped[time] = mapped_column(Time, nullable=False)


class StaffScheduleBulkOperationChange(Base):
    """Immutable audit record of the schedule applied to one employee/date."""

    __tablename__ = "staff_schedule_bulk_operation_changes"

    id: Mapped[int] = mapped_column(_PRIMARY_KEY, primary_key=True)
    bulk_operation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff_schedule_bulk_operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    previous_intervals: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    applied_intervals: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
