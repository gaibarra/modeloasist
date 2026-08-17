"""ORM model for employee schedules."""
from sqlalchemy import BigInteger, Column, ForeignKey, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    employee_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    esc_clave: Mapped[str | None] = mapped_column(Text)
    prog_clave: Mapped[str | None] = mapped_column(Text)
    mat_clave: Mapped[str | None] = mapped_column(Text)
    mat_nombre: Mapped[str | None] = mapped_column(Text)
    gpo_clave: Mapped[str | None] = mapped_column(Text)
    dia_letra: Mapped[str | None] = mapped_column(String(3))
    inicio: Mapped[str] = mapped_column(Time, nullable=False)
    fin: Mapped[str] = mapped_column(Time, nullable=False)
    created_at: Mapped[str] = mapped_column(server_default=func.now())

    employee = relationship("Employee", back_populates="schedules")
