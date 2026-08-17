"""Expose API route modules."""
from app.api.routes import analytics, auth, employees, health, insights, staff

__all__ = ["analytics", "auth", "employees", "health", "insights", "staff"]
