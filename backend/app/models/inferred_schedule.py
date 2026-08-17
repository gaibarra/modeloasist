"""ORM model for inferred schedules built from historical attendance."""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class InferredSchedule(Base):
    __tablename__ = "inferred_schedules"
    __table_args__ = (
        UniqueConstraint("employee_id", "weekday", name="uq_inferred_employee_weekday"),
        {"sqlite_autoincrement": True},
    )

    id = Column(
        Integer().with_variant(BigInteger, "postgresql"),
        primary_key=True,
        index=True,
        autoincrement=True,
    )
    employee_id = Column(BigInteger, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    weekday = Column(SmallInteger, nullable=False)
    expected_time = Column(Time, nullable=False)
    sample_size = Column(Integer, nullable=False)
    confidence = Column(Numeric(5, 2), nullable=False)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    employee = relationship("Employee", backref="inferred_schedules")
