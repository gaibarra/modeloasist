"""ORM models for staff access control and normalized departments."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StaffUser(Base):
    __tablename__ = "staff_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    employee_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("employees.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    employee = relationship("Employee", back_populates="staff_user", uselist=False)
    department_scopes = relationship(
        "StaffDepartmentScope",
        back_populates="staff_user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attendance_import_batches = relationship("AttendanceImportBatch", back_populates="uploaded_by")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    campus: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    aliases = relationship(
        "DepartmentAlias",
        back_populates="department",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    employee_links = relationship(
        "EmployeeDepartment",
        back_populates="department",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    staff_scopes = relationship(
        "StaffDepartmentScope",
        back_populates="department",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DepartmentAlias(Base):
    __tablename__ = "department_aliases"
    __table_args__ = (UniqueConstraint("alias", name="uq_department_aliases_alias"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    department_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="employee")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    department = relationship("Department", back_populates="aliases")


class EmployeeDepartment(Base):
    __tablename__ = "employee_departments"

    employee_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    )
    department_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("departments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    employee = relationship("Employee", back_populates="department_links")
    department = relationship("Department", back_populates="employee_links")


class StaffDepartmentScope(Base):
    __tablename__ = "staff_department_scopes"

    staff_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    department_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("departments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    staff_user = relationship("StaffUser", back_populates="department_scopes")
    department = relationship("Department", back_populates="staff_scopes")