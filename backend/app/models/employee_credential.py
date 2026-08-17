"""Credential storage for employee authentication."""
from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmployeeCredential(Base):
    __tablename__ = "employee_credentials"

    employee_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    employee = relationship("Employee", back_populates="credential")