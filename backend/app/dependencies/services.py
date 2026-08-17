"""FastAPI dependencies for domain services."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.ai_insights import AiInsightsService, get_ai_service
from app.services.attendance_import import AttendanceImportService
from app.services.analytics import AnalyticsService


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


def get_ai_insights_service() -> AiInsightsService:
    settings = get_settings()
    return get_ai_service(settings.ai_project_id, settings.ai_location)


def get_attendance_import_service(db: Session = Depends(get_db)) -> AttendanceImportService:
    settings = get_settings()
    return AttendanceImportService(db=db, settings=settings)
