"""Endpoints that expose AI-assisted insights."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import require_admin_employee
from app.dependencies.services import get_ai_insights_service, get_analytics_service
from app.schemas.employee import EmployeeInsight, EmployeeSummary, ScheduleWindow
from app.schemas.insight import InsightPayload
from app.services.ai_insights import AiInsightsService
from app.services.analytics import AnalyticsService, REPORT_YEAR, REPORT_YEAR_END, REPORT_YEAR_START

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/employee/{employee_id}", response_model=EmployeeInsight)
async def employee_insight(
    employee_id: int,
    start: date | None = None,
    end: date | None = None,
    _: object = Depends(require_admin_employee),
    analytics: AnalyticsService = Depends(get_analytics_service),
    ai_service: AiInsightsService = Depends(get_ai_insights_service),
) -> EmployeeInsight:
    start = max(start or REPORT_YEAR_START, REPORT_YEAR_START)
    end = min(end or date.today(), REPORT_YEAR_END)
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Los reportes solo admiten fechas dentro de {REPORT_YEAR}",
        )
    stats = analytics.employee_stats(employee_id, start, end)
    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado no encontrado")

    schedules = [
        ScheduleWindow(
            dia_letra=schedule.dia_letra,
            inicio=schedule.inicio,
            fin=schedule.fin,
            mat_nombre=schedule.mat_nombre,
            gpo_clave=schedule.gpo_clave,
        )
        for schedule in analytics.schedules_for_employee(employee_id)
    ]
    payload = InsightPayload(
        employee_id=employee_id,
        period_start=start,
        period_end=end,
        punctuality_rank=None,
        punctuality_percentile=None,
        recommendations=[
            "Planifica tu salida con 10 minutos de anticipación",
            "Confirma tus horarios en la app cada lunes",
        ],
        behavior_trends=[],
    )
    ai_feedback = await ai_service.build_employee_coaching(payload)
    employee = EmployeeSummary(id=employee_id, nombre="", departamento="", email="n/a@example.com")
    return EmployeeInsight(
        employee=employee,
        punctuality_score=stats.punctuality_score,
        attendance_rate=1.0,
        ai_feedback=ai_feedback,
        recent_events=[],
        schedule_windows=schedules,
    )
