"""ORM model for cached campus-level weekly KPIs."""
from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, func

from app.db.base import Base


class AttendanceWeeklyMetric(Base):
    __tablename__ = "attendance_weekly_metrics"

    week_start = Column(Date, primary_key=True)
    campus = Column(String, primary_key=True)
    week_end = Column(Date, nullable=False)
    total_events = Column(Integer, nullable=False)
    on_time_events = Column(Integer, nullable=False)
    late_events = Column(Integer, nullable=False)
    punctuality_rate = Column(Numeric(5, 4), nullable=False)
    position = Column(Integer, nullable=False)
    position_delta = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
