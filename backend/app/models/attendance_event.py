"""ORM model for attendance events."""
from datetime import date, datetime, time

from sqlalchemy import BigInteger, Column, Date, ForeignKey, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    departamento_raw: Mapped[str | None] = mapped_column(Text)
    device_name: Mapped[str | None] = mapped_column(Text)
    device_serial: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(64))
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tiempo: Mapped[time] = mapped_column(Time, nullable=False)
    event_ts: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    employee = relationship("Employee", back_populates="attendance_events")
