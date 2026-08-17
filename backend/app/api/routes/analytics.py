"""Routes that expose real analytics snapshots for the dashboard."""
from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import require_admin_employee
from app.dependencies.services import get_analytics_service
from app.schemas.analytics import (
    CampusMetrics,
    DashboardResponse,
    EmployeeRanking,
    EmployeeWeeklyCheckin,
    GlobalMetrics,
    TimelineEntry,
    WeeklyCampusPosition,
    WeeklyCheckinDay,
    WeeklyHistoryRow,
)
from app.services.analytics import AnalyticsService, DashboardSnapshot

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard_snapshot(
    refresh: bool = False,
    _: object = Depends(require_admin_employee),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> DashboardResponse:
    snapshot = analytics.dashboard_snapshot(force_refresh=refresh)
    return _to_response(snapshot)


@router.get("/weekly-history", response_model=list[WeeklyHistoryRow])
def get_weekly_history(
    weeks: int = Query(12, ge=1, le=24),
    refresh: bool = False,
    _: object = Depends(require_admin_employee),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> list[WeeklyHistoryRow]:
    rows = analytics.weekly_history_table(weeks, force_refresh=refresh)
    return [
        WeeklyHistoryRow(
            week_start=row.week_start,
            week_end=row.week_end,
            campuses=[
                WeeklyCampusPosition(
                    campus=campus.campus,
                    position=campus.position,
                    position_delta=campus.position_delta,
                    total_events=campus.total_events,
                    on_time_events=campus.on_time_events,
                    late_events=campus.late_events,
                    punctuality_rate=campus.punctuality_rate,
                )
                for campus in row.campuses
            ],
        )
        for row in rows
    ]


@router.get("/employee-rankings", response_model=list[EmployeeRanking])
def search_employee_rankings(
    days: int | None = Query(None, ge=1, le=366),
    campus: str | None = None,
    department: str | None = None,
    search: str | None = None,
    employeeIds: str | None = None,
    limit: int = Query(100, ge=0, le=100),
    includeWeekly: bool = False,
    weeklyWeeks: int | None = Query(None, ge=1, le=24),
    refresh: bool = False,
    _: object = Depends(require_admin_employee),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> list[EmployeeRanking]:
    employee_ids = _parse_employee_ids(employeeIds)
    rankings = analytics.employee_rankings(
        days=days,
        campus=campus,
        department=department,
        search=search,
        employee_ids=employee_ids,
        limit=limit,
        include_weekly=includeWeekly,
        weekly_weeks=weeklyWeeks,
        force_refresh=refresh,
    )
    return [
        EmployeeRanking(
            id=employee.id,
            nombre=employee.nombre,
            departamento=employee.departamento,
            campus=employee.campus,
            total_days=employee.total_days,
            late_days=employee.late_days,
            punctuality_rate=employee.punctuality_rate,
            entrada=employee.entrada,
            weekly_checkins=_map_weekly_checkins(employee.weekly_checkins),
        )
        for employee in rankings
    ]


def _to_response(snapshot: DashboardSnapshot) -> DashboardResponse:
    return DashboardResponse(
        global_metrics=GlobalMetrics(
            window_start=snapshot.global_metrics.window_start,
            window_end=snapshot.global_metrics.window_end,
            total_events=snapshot.global_metrics.total_events,
            on_time_events=snapshot.global_metrics.on_time_events,
            late_events=snapshot.global_metrics.late_events,
            punctuality_rate=snapshot.global_metrics.punctuality_rate,
            active_employees=snapshot.global_metrics.active_employees,
        ),
        campus_metrics=[
            CampusMetrics(
                campus=campus.campus,
                total_events=campus.total_events,
                active_employees=campus.active_employees,
                on_time_events=campus.on_time_events,
                late_events=campus.late_events,
                punctuality_rate=campus.punctuality_rate,
            )
            for campus in snapshot.campus_metrics
        ],
        top_employees=[
            EmployeeRanking(
                id=employee.id,
                nombre=employee.nombre,
                departamento=employee.departamento,
                campus=employee.campus,
                total_days=employee.total_days,
                late_days=employee.late_days,
                punctuality_rate=employee.punctuality_rate,
                entrada=employee.entrada,
                weekly_checkins=_map_weekly_checkins(employee.weekly_checkins),
            )
            for employee in snapshot.top_employees
        ],
        timeline=[
            TimelineEntry(title=item.title, detail=item.detail, time=item.time)
            for item in snapshot.timeline
        ],
    )


def _map_weekly_checkins(weekly_rows):
    if not weekly_rows:
        return []
    mapped: list[EmployeeWeeklyCheckin] = []
    for week in weekly_rows:
        days = getattr(week, "days", []) or []
        mapped.append(
            EmployeeWeeklyCheckin(
                week_start=week.week_start,
                week_end=week.week_end,
                days=[
                    WeeklyCheckinDay(
                        weekday=day.weekday,
                        entrada=day.entrada,
                        is_late=day.is_late,
                        expected=getattr(day, "expected", None),
                        inferred=getattr(day, "inferred", False),
                    )
                    for day in days
                ],
            )
        )
    return mapped


def _parse_employee_ids(raw_value: str | None) -> list[int] | None:
    if raw_value is None:
        return None
    employee_ids: list[int] = []
    for chunk in raw_value.split(","):
        token = chunk.strip()
        if not token:
            continue
        try:
            employee_id = int(token)
        except ValueError:
            continue
        if employee_id > 0:
            employee_ids.append(employee_id)
    return employee_ids or []
