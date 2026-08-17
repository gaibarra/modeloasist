"""API router factory."""
from fastapi import APIRouter

from app.api.routes import analytics, auth, employees, health, insights, staff


def get_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(auth.router)
    router.include_router(analytics.router)
    router.include_router(employees.router)
    router.include_router(insights.router)
    router.include_router(staff.router)
    return router
