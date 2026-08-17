"""ORM model for employees."""
from sqlalchemy import BigInteger, Column, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(BigInteger, primary_key=True, index=True)
    nombre = Column(Text, nullable=False)
    departamento = Column(Text, nullable=False)
    campus = Column(Text, nullable=True, index=True)
    division = Column(Text, nullable=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)

    schedules = relationship(
        "Schedule",
        back_populates="employee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    credential = relationship(
        "EmployeeCredential",
        back_populates="employee",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    staff_user = relationship(
        "StaffUser",
        back_populates="employee",
        uselist=False,
        passive_deletes=True,
    )
    department_links = relationship(
        "EmployeeDepartment",
        back_populates="employee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attendance_events = relationship(
        "AttendanceEvent",
        back_populates="employee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
