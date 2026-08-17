"""Domain analytics helpers that operate with real attendance data."""
from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from time import monotonic
from typing import Iterable, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.attendance_event import AttendanceEvent
from app.models.attendance_weekly_metric import AttendanceWeeklyMetric
from app.models.employee import Employee
from app.models.inferred_schedule import InferredSchedule
from app.models.schedule import Schedule
from app.models.staff_access import Department, EmployeeDepartment
from app.services.department_normalization import derive_department_campus

REPORT_YEAR = 2026
REPORT_YEAR_START = date(REPORT_YEAR, 1, 1)
REPORT_YEAR_END = date(REPORT_YEAR, 12, 31)

CAMPUS_WHITELIST = ("Mérida", "Montejo", "Chetumal", "Valladolid")
DEPARTMENT_SCHEDULE_OVERRIDES = {
    "MTJ-Contabilidad": time(hour=7, minute=0),
    "Escuela Modelo/Montejo/MTJ-Contabilidad": time(hour=7, minute=0),
}
DAY_TO_INDEX = {
    "Lunes": 0,
    "Martes": 1,
    "Miércoles": 2,
    "Jueves": 3,
    "Viernes": 4,
    "Sábado": 5,
    "Domingo": 6,
}
LATE_TOLERANCE_MINUTES = 10
SCHEDULE_CONSECUTIVE_GAP_MINUTES = 10

_ANALYTICS_CACHE: dict[tuple[object, ...], tuple[float, object]] = {}
_CACHE_TTLS = {
    "dashboard": 120,
    "weekly_history": 300,
    "employee_rankings": 180,
}


def _cache_get(key: tuple[object, ...]):
    cached = _ANALYTICS_CACHE.get(key)
    if not cached:
        return None
    expires_at, value = cached
    if monotonic() >= expires_at:
        _ANALYTICS_CACHE.pop(key, None)
        return None
    return copy.deepcopy(value)


def _cache_set(key: tuple[object, ...], value: object, ttl_key: str):
    ttl = _CACHE_TTLS.get(ttl_key, 60)
    _ANALYTICS_CACHE[key] = (monotonic() + ttl, copy.deepcopy(value))
    return copy.deepcopy(value)


@dataclass
class CampusSnapshot:
    campus: str
    total_events: int = 0
    active_employees: int = 0
    on_time_events: int = 0
    late_events: int = 0

    @property
    def punctuality_rate(self) -> float:
        total_flagged = self.on_time_events + self.late_events
        return self.on_time_events / total_flagged if total_flagged else 1.0


@dataclass
class GlobalMetrics:
    window_start: date
    window_end: date
    total_events: int
    on_time_events: int
    late_events: int
    active_employees: int

    @property
    def punctuality_rate(self) -> float:
        total_flagged = self.on_time_events + self.late_events
        return self.on_time_events / total_flagged if total_flagged else 1.0


@dataclass
class WeeklyCheckinDay:
    weekday: int
    entrada: time | None
    is_late: bool | None
    expected: time | None
    inferred: bool = False


@dataclass
class EmployeeWeeklyCheckin:
    week_start: date
    week_end: date
    days: list[WeeklyCheckinDay]


@dataclass
class EmployeeRanking:
    id: int
    nombre: str
    departamento: str
    campus: str
    total_days: int
    late_days: int
    entrada: time | None = None
    weekly_checkins: list[EmployeeWeeklyCheckin] | None = None

    @property
    def punctuality_rate(self) -> float:
        return (self.total_days - self.late_days) / self.total_days if self.total_days else 1.0


@dataclass
class TimelineHighlight:
    title: str
    detail: str
    time: str


@dataclass
class ClassifiedEntry:
    employee_id: int
    employee_name: str
    departamento: str
    campus: str
    fecha: date
    entrada: time
    is_late: bool


@dataclass
class DashboardSnapshot:
    global_metrics: GlobalMetrics
    campus_metrics: list[CampusSnapshot]
    top_employees: list[EmployeeRanking]
    timeline: list[TimelineHighlight]


@dataclass
class EmployeeAttendanceRecord:
    employee: EmployeeRanking
    recent_events: list[AttendanceEvent]


@dataclass
class WeeklyCampusPosition:
    campus: str
    position: int
    position_delta: int
    total_events: int
    on_time_events: int
    late_events: int
    punctuality_rate: float


@dataclass
class WeeklyHistoryRow:
    week_start: date
    week_end: date
    campuses: list[WeeklyCampusPosition]


@dataclass
class StaffDailyAttendanceRow:
    employee_id: int
    employee_name: str
    employee_email: str
    department_id: int
    department_name: str
    campus: str | None
    date: date
    first_event: time | None
    last_event: time | None
    entry_event: time | None
    exit_event: time | None
    entry_event_inferred: bool
    exit_event_inferred: bool
    total_events: int
    scheduled_start: time | None
    scheduled_end: time | None
    status: str
    schedule_intervals: list[StaffScheduleInterval] = field(default_factory=list)
    has_mixed_schedule: bool = False


@dataclass
class StaffPeriodAttendanceDay:
    date: date
    first_event: time | None
    last_event: time | None
    entry_event: time | None
    exit_event: time | None
    entry_event_inferred: bool
    exit_event_inferred: bool
    total_events: int
    scheduled_start: time | None
    scheduled_end: time | None
    status: str
    schedule_intervals: list[StaffScheduleInterval] = field(default_factory=list)
    has_mixed_schedule: bool = False


@dataclass
class StaffPeriodAttendanceRow:
    employee_id: int
    employee_name: str
    employee_email: str | None
    department_id: int
    department_name: str
    campus: str | None
    total_events: int
    active_days: int
    period_start: date
    period_end: date
    days: list[StaffPeriodAttendanceDay]


@dataclass
class StaffScheduleInterval:
    start: time
    end: time


class AnalyticsService:
    """Runs SQL-level analytics backed by the real asistencia database."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _report_year_filter(self):
        return AttendanceEvent.fecha.between(REPORT_YEAR_START, REPORT_YEAR_END)

    def _merge_with_report_year(self, extra_filter=None):
        report_filter = self._report_year_filter()
        if extra_filter is None:
            return report_filter
        return and_(report_filter, extra_filter)

    def _clamp_window(self, start: date, end: date) -> tuple[date, date]:
        return max(start, REPORT_YEAR_START), min(end, REPORT_YEAR_END)

    def dashboard_snapshot(self, days: int = 30, *, force_refresh: bool = False) -> DashboardSnapshot:
        cache_key = ("dashboard", days, min(date.today(), REPORT_YEAR_END))
        if not force_refresh:
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached
        window_end = min(date.today(), REPORT_YEAR_END)
        window_start = window_end - timedelta(days=days - 1)
        window_start, window_end = self._clamp_window(window_start, window_end)
        window_filter = self._merge_with_report_year(
            AttendanceEvent.fecha.between(window_start, window_end)
        )

        campus_event_counts = self._campus_event_counts(window_filter)
        campus_employee_counts = self._campus_employee_counts(window_filter)
        total_events = sum(campus_event_counts.get(campus, 0) for campus in CAMPUS_WHITELIST)
        active_employees = sum(
            campus_employee_counts.get(campus, 0) for campus in CAMPUS_WHITELIST
        )
        classified_entries = self._classify_first_entries(window_filter)
        campus_snapshots = self._build_campus_snapshots(
            campus_event_counts, campus_employee_counts, classified_entries
        )

        global_metrics = GlobalMetrics(
            window_start=window_start,
            window_end=window_end,
            total_events=total_events,
            on_time_events=sum(snapshot.on_time_events for snapshot in campus_snapshots.values()),
            late_events=sum(snapshot.late_events for snapshot in campus_snapshots.values()),
            active_employees=active_employees,
        )

        top_employees = self._build_top_employees(classified_entries)
        timeline = self._build_timeline(window_end, classified_entries)

        ordered_snapshots = [campus_snapshots[name] for name in CAMPUS_WHITELIST]

        snapshot = DashboardSnapshot(
            global_metrics=global_metrics,
            campus_metrics=ordered_snapshots,
            top_employees=top_employees,
            timeline=timeline,
        )
        return _cache_set(cache_key, snapshot, "dashboard")

    def weekly_history_table(self, weeks: int = 12, *, force_refresh: bool = False) -> list[WeeklyHistoryRow]:
        if weeks <= 0:
            weeks = 1
        cache_key = ("weekly_history", weeks, min(date.today(), REPORT_YEAR_END))
        if not force_refresh:
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached
        today = min(date.today(), REPORT_YEAR_END)
        current_monday = today - timedelta(days=today.weekday())
        week_starts = sorted({current_monday - timedelta(days=7 * i) for i in range(weeks)})
        week_starts = [week for week in week_starts if REPORT_YEAR_START <= week <= REPORT_YEAR_END]
        if not week_starts:
            return []
        window_start = week_starts[0]
        window_end = current_monday + timedelta(days=6)
        window_start, window_end = self._clamp_window(window_start, window_end)
        window_filter = self._merge_with_report_year(
            AttendanceEvent.fecha.between(window_start, window_end)
        )

        entries = self._classify_first_entries(window_filter)
        if not entries:
            return []

        latest_entry_date = max(entry.fecha for entry in entries)
        latest_week_start = latest_entry_date - timedelta(days=latest_entry_date.weekday())
        week_starts = [week for week in week_starts if week <= latest_week_start]
        if not week_starts:
            return []

        weekly_counts: dict[tuple[date, str], dict[str, int]] = defaultdict(
            lambda: {"on_time": 0, "late": 0}
        )
        for entry in entries:
            campus = entry.campus
            if campus not in CAMPUS_WHITELIST:
                continue
            week_start = entry.fecha - timedelta(days=entry.fecha.weekday())
            key = (week_start, campus)
            if entry.is_late:
                weekly_counts[key]["late"] += 1
            else:
                weekly_counts[key]["on_time"] += 1

        history_rows: list[WeeklyHistoryRow] = []
        previous_positions: dict[str, int] = {}
        for week_start in week_starts:
            week_end = week_start + timedelta(days=6)
            campus_positions: list[WeeklyCampusPosition] = []
            for campus in CAMPUS_WHITELIST:
                stats = weekly_counts.get((week_start, campus), {"on_time": 0, "late": 0})
                on_time = stats.get("on_time", 0)
                late = stats.get("late", 0)
                total = on_time + late
                punctuality_rate = on_time / total if total else 0.0
                campus_positions.append(
                    WeeklyCampusPosition(
                        campus=campus,
                        position=0,
                        position_delta=0,
                        total_events=total,
                        on_time_events=on_time,
                        late_events=late,
                        punctuality_rate=punctuality_rate,
                    )
                )
            campus_positions.sort(
                key=lambda row: (row.punctuality_rate, row.on_time_events - row.late_events),
                reverse=True,
            )
            for idx, row in enumerate(campus_positions, start=1):
                prev_pos = previous_positions.get(row.campus)
                row.position = idx
                row.position_delta = (prev_pos - idx) if prev_pos else 0

            week_total_events = sum(campus.total_events for campus in campus_positions)
            if week_total_events == 0:
                continue

            previous_positions = {row.campus: row.position for row in campus_positions}
            history_rows.append(
                WeeklyHistoryRow(week_start=week_start, week_end=week_end, campuses=campus_positions)
            )

        self._persist_weekly_metrics(history_rows)
        history_rows.sort(key=lambda row: row.week_start, reverse=True)
        return _cache_set(cache_key, history_rows, "weekly_history")

    def _persist_weekly_metrics(self, rows: list[WeeklyHistoryRow]) -> None:
        if not rows:
            return
        payloads: list[dict[str, object]] = []
        for row in rows:
            for campus in row.campuses:
                payloads.append(
                    {
                        "week_start": row.week_start,
                        "week_end": row.week_end,
                        "campus": campus.campus,
                        "total_events": campus.total_events,
                        "on_time_events": campus.on_time_events,
                        "late_events": campus.late_events,
                        "punctuality_rate": campus.punctuality_rate,
                        "position": campus.position,
                        "position_delta": campus.position_delta,
                    }
                )
        if not payloads:
            return
        insert_stmt = insert(AttendanceWeeklyMetric).values(payloads)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[AttendanceWeeklyMetric.week_start, AttendanceWeeklyMetric.campus],
            set_={
                "week_end": insert_stmt.excluded.week_end,  # type: ignore[attr-defined]
                "total_events": insert_stmt.excluded.total_events,  # type: ignore[attr-defined]
                "on_time_events": insert_stmt.excluded.on_time_events,  # type: ignore[attr-defined]
                "late_events": insert_stmt.excluded.late_events,  # type: ignore[attr-defined]
                "punctuality_rate": insert_stmt.excluded.punctuality_rate,  # type: ignore[attr-defined]
                "position": insert_stmt.excluded.position,  # type: ignore[attr-defined]
                "position_delta": insert_stmt.excluded.position_delta,  # type: ignore[attr-defined]
                "created_at": func.now(),
            },
        )
        self._db.execute(stmt)
        self._db.flush()
        self._db.commit()

    def _campus_event_counts(self, window_filter) -> dict[str, int]:
        stmt = (
            select(Employee.campus, Employee.departamento, func.count().label("total"))
            .join(AttendanceEvent, AttendanceEvent.employee_id == Employee.id)
            .where(window_filter)
            .where(_campus_filter_clause())
            .group_by(Employee.campus, Employee.departamento)
        )
        counts: dict[str, int] = defaultdict(int)
        for campus_value, departamento, total in self._db.execute(stmt):
            campus = campus_value or _campus_from_department(departamento)
            counts[campus] += int(total)
        return counts

    def _campus_employee_counts(self, window_filter) -> dict[str, int]:
        distinct_employees = func.count(func.distinct(AttendanceEvent.employee_id))
        stmt = (
            select(Employee.campus, Employee.departamento, distinct_employees.label("total"))
            .join(AttendanceEvent, AttendanceEvent.employee_id == Employee.id)
            .where(window_filter)
            .where(_campus_filter_clause())
            .group_by(Employee.campus, Employee.departamento)
        )
        counts: dict[str, int] = defaultdict(int)
        for campus_value, departamento, total in self._db.execute(stmt):
            campus = campus_value or _campus_from_department(departamento)
            counts[campus] += int(total)
        return counts

    def _classify_first_entries(self, window_filter=None) -> list[ClassifiedEntry]:
        stmt = (
            select(
                AttendanceEvent.employee_id,
                Employee.nombre,
                Employee.departamento,
                Employee.campus,
                AttendanceEvent.fecha,
                func.min(AttendanceEvent.tiempo).label("primera_hora"),
            )
            .join(Employee, Employee.id == AttendanceEvent.employee_id)
            .where(_campus_filter_clause())
            .group_by(
                AttendanceEvent.employee_id,
                AttendanceEvent.fecha,
                Employee.nombre,
                Employee.departamento,
                Employee.campus,
            )
        )
        stmt = stmt.where(self._merge_with_report_year(window_filter))
        rows = self._db.execute(stmt).all()
        employee_ids = {row.employee_id for row in rows}
        schedule_map = self._schedule_map(employee_ids)
        schedule_map, _ = self._fill_schedule_map_with_inference(schedule_map, rows)
        entries: list[ClassifiedEntry] = []
        for row in rows:
            campus = row.campus or _campus_from_department(row.departamento)
            weekday_index = row.fecha.weekday()
            scheduled = schedule_map.get((row.employee_id, weekday_index))
            is_late = _is_late(row.primera_hora, scheduled)
            entries.append(
                ClassifiedEntry(
                    employee_id=row.employee_id,
                    employee_name=row.nombre,
                    departamento=row.departamento,
                    campus=campus,
                    fecha=row.fecha,
                    entrada=row.primera_hora,
                    is_late=is_late,
                )
            )
        return entries

    def _schedule_map(self, employee_ids: Iterable[int]) -> dict[tuple[int, int], time]:
        if not employee_ids:
            return {}
        ids = [employee_id for employee_id in employee_ids if employee_id]
        if not ids:
            return {}
        stmt = (
            select(Schedule.employee_id, Schedule.dia_letra, func.min(Schedule.inicio))
            .where(Schedule.employee_id.in_(ids))
            .group_by(Schedule.employee_id, Schedule.dia_letra)
        )
        mapping: dict[tuple[int, int], time] = {}
        for employee_id, dia_letra, inicio in self._db.execute(stmt):
            day_index = _day_to_index(dia_letra)
            if day_index is None:
                continue
            mapping[(employee_id, day_index)] = inicio
        self._apply_department_overrides(mapping, ids)
        return mapping

    def _employees_with_registered_schedule(self, employee_ids: Iterable[int]) -> set[int]:
        ids = {employee_id for employee_id in employee_ids if employee_id}
        if not ids:
            return set()
        stmt = (
            select(func.distinct(Schedule.employee_id))
            .where(Schedule.employee_id.in_(list(ids)))
        )
        return {int(employee_id) for (employee_id,) in self._db.execute(stmt)}

    def _apply_department_overrides(
        self,
        mapping,
        employee_ids: Iterable[int],
        *,
        primary_only: bool = False,
    ) -> None:
        ids = {employee_id for employee_id in employee_ids if employee_id}
        if not ids or not DEPARTMENT_SCHEDULE_OVERRIDES:
            return
        stmt = (
            select(Employee.id, Employee.departamento)
            .where(Employee.id.in_(list(ids)))
            .where(Employee.departamento.in_(DEPARTMENT_SCHEDULE_OVERRIDES.keys()))
        )
        for employee_id, departamento in self._db.execute(stmt):
            override = DEPARTMENT_SCHEDULE_OVERRIDES.get(departamento)
            if not override:
                continue
            if primary_only:
                mapping[int(employee_id)] = override
            else:
                for weekday in range(5):  # Monday-Friday only for overrides
                    mapping[(int(employee_id), weekday)] = override

    def _fill_schedule_map_with_inference(
        self,
        schedule_map: dict[tuple[int, int], time],
        rows: Sequence,
    ) -> tuple[dict[tuple[int, int], time], set[tuple[int, int]]]:
        if not rows:
            return schedule_map, set()
        missing_keys = {
            (row.employee_id, row.fecha.weekday())
            for row in rows
            if (row.employee_id, row.fecha.weekday()) not in schedule_map
        }
        if not missing_keys:
            return schedule_map, set()

        candidate_ids = {employee_id for employee_id, _ in missing_keys}
        registered_ids = self._employees_with_registered_schedule(candidate_ids)
        if registered_ids:
            missing_keys = {key for key in missing_keys if key[0] not in registered_ids}
        if not missing_keys:
            return schedule_map, set()

        employee_subset = {employee_id for employee_id, _ in missing_keys}
        stored = self._fetch_inferred_schedule_map(employee_subset)
        inferred_keys: set[tuple[int, int]] = set()
        for key, expected in stored.items():
            if key in missing_keys:
                schedule_map[key] = expected
                inferred_keys.add(key)

        remaining = {key for key in missing_keys if key not in schedule_map}
        if not remaining:
            return schedule_map, inferred_keys

        payloads = self._compute_inferred_payloads(rows, remaining)
        if payloads:
            insert_stmt = insert(InferredSchedule).values(payloads)
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=[InferredSchedule.employee_id, InferredSchedule.weekday],
                set_={
                    "expected_time": insert_stmt.excluded.expected_time,  # type: ignore[attr-defined]
                    "sample_size": insert_stmt.excluded.sample_size,  # type: ignore[attr-defined]
                    "confidence": insert_stmt.excluded.confidence,  # type: ignore[attr-defined]
                    "calculated_at": func.now(),
                },
            )
            self._db.execute(stmt)
            self._db.flush()
            self._db.commit()
            for payload in payloads:
                schedule_map[(payload["employee_id"], payload["weekday"])] = payload["expected_time"]
                inferred_keys.add((payload["employee_id"], payload["weekday"]))
        return schedule_map, inferred_keys

    def _fetch_inferred_schedule_map(
        self, employee_ids: set[int]
    ) -> dict[tuple[int, int], time]:
        if not employee_ids:
            return {}
        stmt = select(
            InferredSchedule.employee_id,
            InferredSchedule.weekday,
            InferredSchedule.expected_time,
        ).where(InferredSchedule.employee_id.in_(list(employee_ids)))
        inferred: dict[tuple[int, int], time] = {}
        for employee_id, weekday, expected in self._db.execute(stmt):
            inferred[(employee_id, weekday)] = _round_to_clean_slot(expected)
        return inferred

    def _compute_inferred_payloads(
        self,
        rows: Sequence,
        remaining: set[tuple[int, int]],
    ) -> list[dict[str, object]]:
        buckets: dict[tuple[int, int], list[time]] = defaultdict(list)
        employee_stats: dict[int, _ScheduleInferenceStats] = {}
        for row in rows:
            weekday = row.fecha.weekday()
            key = (row.employee_id, weekday)
            if key in remaining:
                buckets[key].append(row.primera_hora)
            stats = employee_stats.setdefault(row.employee_id, _ScheduleInferenceStats())
            if stats.earliest is None or row.primera_hora < stats.earliest:
                stats.earliest = row.primera_hora
            nearest_slot = _round_to_nearest_slot(row.primera_hora)
            if nearest_slot:
                stats.slot_counts[nearest_slot] = stats.slot_counts.get(nearest_slot, 0) + 1
            stats.total_minutes += _time_to_minutes(row.primera_hora)
            stats.samples += 1
        payloads: list[dict[str, object]] = []
        for key, times in buckets.items():
            if not times:
                continue
            stats = employee_stats.get(key[0])
            base_expected = _select_expected_from_stats(stats) or min(times)
            expected = _round_to_clean_slot(base_expected)
            sample_size = len(times)
            confidence = min(0.99, sample_size / 10)
            payloads.append(
                {
                    "employee_id": key[0],
                    "weekday": key[1],
                    "expected_time": expected,
                    "sample_size": sample_size,
                    "confidence": round(confidence, 2),
                }
            )
        return payloads

    def _build_campus_snapshots(
        self,
        campus_event_counts: dict[str, int],
        campus_employee_counts: dict[str, int],
        entries: list[ClassifiedEntry],
    ) -> dict[str, CampusSnapshot]:
        snapshots = {campus: CampusSnapshot(campus=campus) for campus in CAMPUS_WHITELIST}
        for campus, total in campus_event_counts.items():
            if campus in snapshots:
                snapshots[campus].total_events = total
        for campus, total in campus_employee_counts.items():
            if campus in snapshots:
                snapshots[campus].active_employees = total
        for entry in entries:
            snapshot = snapshots.get(entry.campus)
            if not snapshot:
                continue
            if entry.is_late:
                snapshot.late_events += 1
            else:
                snapshot.on_time_events += 1
        return snapshots

    def employee_rankings(
        self,
        days: int | None = None,
        campus: str | None = None,
        department: str | None = None,
        search: str | None = None,
        employee_ids: Sequence[int] | None = None,
        limit: int = 200,
        include_weekly: bool = False,
        weekly_weeks: int | None = None,
        *,
        force_refresh: bool = False,
    ) -> list[EmployeeRanking]:
        if include_weekly and weekly_weeks is None:
            weekly_weeks = 12
        normalized_employee_ids = tuple(sorted({employee_id for employee_id in (employee_ids or []) if employee_id > 0}))
        if employee_ids is not None and not normalized_employee_ids:
            return []
        cache_key = (
            "employee_rankings",
            days,
            campus or "",
            department or "",
            (search or "").strip().lower(),
            normalized_employee_ids,
            limit,
            include_weekly,
            weekly_weeks,
            min(date.today(), REPORT_YEAR_END),
        )
        if not force_refresh:
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached
        window_filter = self._report_year_filter()
        if days is not None:
            if days <= 0:
                days = 1
            window_end = min(date.today(), REPORT_YEAR_END)
            window_start = window_end - timedelta(days=days - 1)
            window_start, window_end = self._clamp_window(window_start, window_end)
            window_filter = self._merge_with_report_year(
                AttendanceEvent.fecha.between(window_start, window_end)
            )
        if normalized_employee_ids:
            window_filter = and_(window_filter, AttendanceEvent.employee_id.in_(list(normalized_employee_ids)))

        entries = self._classify_first_entries(window_filter)
        rankings = self._build_top_employees(entries, limit=None, min_days=0)
        ranking_map = {ranking.id: ranking for ranking in rankings}

        employee_stmt = (
            select(
                Employee.id.label("employee_id"),
                Employee.nombre.label("nombre"),
                Employee.departamento.label("departamento"),
                Employee.campus.label("campus"),
            )
            .where(_campus_filter_clause())
            .order_by(Employee.nombre)
        )
        if normalized_employee_ids:
            employee_stmt = employee_stmt.where(Employee.id.in_(list(normalized_employee_ids)))
        employee_rows = self._db.execute(employee_stmt).all()
        employee_ids = [row.employee_id for row in employee_rows]
        schedule_map_all = self._primary_schedule_map(employee_ids)

        for ranking in rankings:
            ranking.entrada = schedule_map_all.get(ranking.id)
        
        search_lc = (search or "").strip().lower()
        department_lc = (department or "").strip().lower()
        campus_filter = (campus or "").strip()

        filtered: list[EmployeeRanking] = []
        for row in employee_rows:
            campus_value = row.campus or _campus_from_department(row.departamento)
            ranking = ranking_map.get(row.employee_id)
            current = ranking or EmployeeRanking(
                id=row.employee_id,
                nombre=row.nombre,
                departamento=row.departamento,
                campus=campus_value,
                total_days=0,
                late_days=0,
            )
            current.entrada = schedule_map_all.get(row.employee_id)

            if campus_filter and current.campus != campus_filter:
                continue
            if department_lc and department_lc not in (current.departamento or "").lower():
                continue
            if search_lc and search_lc not in current.nombre.lower():
                continue
            filtered.append(current)

        if include_weekly:
            weekly_map = self._weekly_checkins_for_employees(
                [ranking.id for ranking in filtered], weekly_weeks
            )
            for ranking in filtered:
                ranking.weekly_checkins = weekly_map.get(ranking.id, [])

        if limit > 0:
            return _cache_set(cache_key, filtered[: limit], "employee_rankings")
        return _cache_set(cache_key, filtered, "employee_rankings")

    def employee_attendance_record(
        self,
        employee_id: int,
        *,
        weekly_weeks: int = 12,
        recent_limit: int = 30,
    ) -> EmployeeAttendanceRecord | None:
        employee_row = (
            self._db.execute(
                select(
                    Employee.id.label("employee_id"),
                    Employee.nombre.label("nombre"),
                    Employee.departamento.label("departamento"),
                    Employee.campus.label("campus"),
                ).where(Employee.id == employee_id)
            )
            .mappings()
            .first()
        )
        if employee_row is None:
            return None

        employee_filter = and_(AttendanceEvent.employee_id == employee_id, self._report_year_filter())
        entries = self._classify_first_entries(employee_filter)
        ranking = self._build_top_employees(entries, limit=None, min_days=0)
        current = next((item for item in ranking if item.id == employee_id), None)
        campus_value = employee_row["campus"] or _campus_from_department(employee_row["departamento"])
        if current is None:
            current = EmployeeRanking(
                id=employee_row["employee_id"],
                nombre=employee_row["nombre"],
                departamento=employee_row["departamento"],
                campus=campus_value,
                total_days=0,
                late_days=0,
            )
        primary_schedule = self._primary_schedule_map([employee_id])
        current.entrada = primary_schedule.get(employee_id)
        current.weekly_checkins = self._weekly_checkins_for_employees([employee_id], weekly_weeks).get(
            employee_id,
            [],
        )

        recent_stmt = (
            select(AttendanceEvent)
            .join(Employee, Employee.id == AttendanceEvent.employee_id)
            .where(
                and_(
                    AttendanceEvent.employee_id == employee_id,
                    _campus_filter_clause(),
                    self._report_year_filter(),
                )
            )
            .order_by(AttendanceEvent.event_ts.desc())
            .limit(recent_limit)
        )
        recent_events = list(self._db.scalars(recent_stmt).all())
        return EmployeeAttendanceRecord(employee=current, recent_events=recent_events)

    def staff_daily_attendance(
        self,
        *,
        target_date: date,
        department_id: int,
        employee_ids: Sequence[int] | None = None,
    ) -> list[StaffDailyAttendanceRow]:
        stmt = (
            select(
                Employee.id.label("employee_id"),
                Employee.nombre.label("employee_name"),
                Employee.email.label("employee_email"),
                Employee.campus.label("campus"),
                Employee.departamento.label("legacy_department"),
                Department.id.label("department_id"),
                Department.name.label("department_name"),
                func.min(AttendanceEvent.tiempo).label("first_event"),
                func.max(AttendanceEvent.tiempo).label("last_event"),
                func.count(AttendanceEvent.id).label("total_events"),
            )
            .join(EmployeeDepartment, EmployeeDepartment.employee_id == Employee.id)
            .join(Department, Department.id == EmployeeDepartment.department_id)
            .outerjoin(
                AttendanceEvent,
                and_(AttendanceEvent.employee_id == Employee.id, AttendanceEvent.fecha == target_date),
            )
            .where(EmployeeDepartment.department_id == department_id)
            .group_by(
                Employee.id,
                Employee.nombre,
                Employee.email,
                Employee.campus,
                Employee.departamento,
                Department.id,
                Department.name,
            )
            .order_by(Employee.nombre.asc())
        )
        if employee_ids is not None:
            normalized_ids = [employee_id for employee_id in employee_ids if employee_id > 0]
            if not normalized_ids:
                return []
            stmt = stmt.where(Employee.id.in_(normalized_ids))
        rows = self._db.execute(stmt).all()
        if not rows:
            return []

        employee_ids_for_schedule = [int(row.employee_id) for row in rows]
        schedule_interval_map = self._normalized_schedule_interval_map(employee_ids_for_schedule)

        payload: list[StaffDailyAttendanceRow] = []
        for row in rows:
            intervals = schedule_interval_map.get((int(row.employee_id), target_date.weekday()), [])
            scheduled_start, scheduled_end = _schedule_bounds(intervals)
            first_event = row.first_event
            last_event = row.last_event
            entry_event, exit_event, entry_event_inferred, exit_event_inferred = _resolve_entry_exit_events(
                first_event=first_event,
                last_event=last_event,
                schedule_intervals=intervals,
            )
            total_events = int(row.total_events or 0)
            status = _staff_daily_status(
                first_event=first_event,
                last_event=last_event,
                total_events=total_events,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
            )
            payload.append(
                StaffDailyAttendanceRow(
                    employee_id=int(row.employee_id),
                    employee_name=row.employee_name,
                    employee_email=row.employee_email,
                    department_id=int(row.department_id),
                    department_name=row.department_name,
                    campus=row.campus or _campus_from_department(row.legacy_department),
                    date=target_date,
                    first_event=first_event,
                    last_event=last_event,
                    entry_event=entry_event,
                    exit_event=exit_event,
                    entry_event_inferred=entry_event_inferred,
                    exit_event_inferred=exit_event_inferred,
                    total_events=total_events,
                    scheduled_start=scheduled_start,
                    scheduled_end=scheduled_end,
                    schedule_intervals=intervals,
                    has_mixed_schedule=len(intervals) > 1,
                    status=status,
                )
            )
        return payload

    def staff_period_attendance(
        self,
        *,
        period_start: date,
        period_end: date,
        department_id: int,
        employee_ids: Sequence[int] | None = None,
    ) -> list[StaffPeriodAttendanceRow]:
        employee_stmt = (
            select(
                Employee.id.label("employee_id"),
                Employee.nombre.label("employee_name"),
                Employee.email.label("employee_email"),
                Employee.campus.label("campus"),
                Employee.departamento.label("legacy_department"),
                Department.id.label("department_id"),
                Department.name.label("department_name"),
            )
            .join(EmployeeDepartment, EmployeeDepartment.employee_id == Employee.id)
            .join(Department, Department.id == EmployeeDepartment.department_id)
            .where(EmployeeDepartment.department_id == department_id)
            .order_by(Employee.nombre.asc())
        )
        if employee_ids is not None:
            normalized_ids = [employee_id for employee_id in employee_ids if employee_id > 0]
            if not normalized_ids:
                return []
            employee_stmt = employee_stmt.where(Employee.id.in_(normalized_ids))

        employee_rows = self._db.execute(employee_stmt).all()
        if not employee_rows:
            return []

        employee_id_list = [int(row.employee_id) for row in employee_rows]

        event_rows = self._db.execute(
            select(
                AttendanceEvent.employee_id,
                AttendanceEvent.fecha,
                func.min(AttendanceEvent.tiempo).label("first_event"),
                func.max(AttendanceEvent.tiempo).label("last_event"),
                func.count(AttendanceEvent.id).label("total_events"),
            )
            .where(AttendanceEvent.employee_id.in_(employee_id_list))
            .where(AttendanceEvent.fecha.between(period_start, period_end))
            .group_by(AttendanceEvent.employee_id, AttendanceEvent.fecha)
        ).all()
        event_map = {
            (int(row.employee_id), row.fecha): (
                row.first_event,
                row.last_event,
                int(row.total_events or 0),
            )
            for row in event_rows
        }

        schedule_interval_map = self._normalized_schedule_interval_map(employee_id_list)

        all_dates = _daterange(period_start, period_end)
        payload: list[StaffPeriodAttendanceRow] = []
        for row in employee_rows:
            day_payload: list[StaffPeriodAttendanceDay] = []
            employee_total_events = 0
            active_days = 0
            for current_date in all_dates:
                first_event, last_event, total_events = event_map.get((int(row.employee_id), current_date), (None, None, 0))
                intervals = schedule_interval_map.get((int(row.employee_id), current_date.weekday()), [])
                scheduled_start, scheduled_end = _schedule_bounds(intervals)
                entry_event, exit_event, entry_event_inferred, exit_event_inferred = _resolve_entry_exit_events(
                    first_event=first_event,
                    last_event=last_event,
                    schedule_intervals=intervals,
                )
                status = _staff_daily_status(
                    first_event=first_event,
                    last_event=last_event,
                    total_events=total_events,
                    scheduled_start=scheduled_start,
                    scheduled_end=scheduled_end,
                )
                if total_events > 0:
                    active_days += 1
                employee_total_events += total_events
                day_payload.append(
                    StaffPeriodAttendanceDay(
                        date=current_date,
                        first_event=first_event,
                        last_event=last_event,
                        entry_event=entry_event,
                        exit_event=exit_event,
                        entry_event_inferred=entry_event_inferred,
                        exit_event_inferred=exit_event_inferred,
                        total_events=total_events,
                        scheduled_start=scheduled_start,
                        scheduled_end=scheduled_end,
                        schedule_intervals=intervals,
                        has_mixed_schedule=len(intervals) > 1,
                        status=status,
                    )
                )

            payload.append(
                StaffPeriodAttendanceRow(
                    employee_id=int(row.employee_id),
                    employee_name=row.employee_name,
                    employee_email=row.employee_email,
                    department_id=int(row.department_id),
                    department_name=row.department_name,
                    campus=row.campus or _campus_from_department(row.legacy_department),
                    total_events=employee_total_events,
                    active_days=active_days,
                    period_start=period_start,
                    period_end=period_end,
                    days=day_payload,
                )
            )
        return payload

    def _normalized_schedule_interval_map(
        self,
        employee_ids: Iterable[int],
    ) -> dict[tuple[int, int], list[StaffScheduleInterval]]:
        ids = [employee_id for employee_id in employee_ids if employee_id]
        if not ids:
            return {}
        rows = self._db.execute(
            select(
                Schedule.employee_id,
                Schedule.dia_letra,
                Schedule.inicio,
                Schedule.fin,
            )
            .where(Schedule.employee_id.in_(ids))
            .order_by(Schedule.employee_id.asc(), Schedule.dia_letra.asc(), Schedule.inicio.asc(), Schedule.fin.asc())
        ).all()
        grouped: dict[tuple[int, int], list[tuple[time, time]]] = defaultdict(list)
        for employee_id, dia_letra, start_time, end_time in rows:
            weekday = _day_to_index(dia_letra)
            if weekday is None or start_time is None or end_time is None:
                continue
            grouped[(int(employee_id), weekday)].append((start_time, end_time))
        return {key: _merge_schedule_intervals(intervals) for key, intervals in grouped.items()}

    def _build_top_employees(
        self,
        entries: list[ClassifiedEntry],
        limit: int | None = 5,
        min_days: int = 3,
    ) -> list[EmployeeRanking]:
        aggregates: dict[int, _EmployeeAccumulator] = {}
        for entry in entries:
            if entry.campus not in CAMPUS_WHITELIST:
                continue
            bucket = aggregates.get(entry.employee_id)
            if not bucket:
                bucket = _EmployeeAccumulator(
                    employee_id=entry.employee_id,
                    nombre=entry.employee_name,
                    departamento=entry.departamento,
                    campus=entry.campus,
                )
                aggregates[entry.employee_id] = bucket
            bucket.add(entry.is_late)
        rankings = [bucket.to_ranking() for bucket in aggregates.values() if bucket.total_days >= min_days]
        schedule_map = self._primary_schedule_map({ranking.id for ranking in rankings})
        for ranking in rankings:
            ranking.entrada = schedule_map.get(ranking.id)
        rankings.sort(
            key=lambda ranking: (ranking.punctuality_rate, ranking.total_days, -ranking.late_days),
            reverse=True,
        )
        if limit is None:
            return rankings
        return rankings[:limit]

    def _weekly_checkins_for_employees(
        self,
        employee_ids: Sequence[int],
        weeks: int | None = None,
    ) -> dict[int, list[EmployeeWeeklyCheckin]]:
        ids = [employee_id for employee_id in employee_ids if employee_id]
        if not ids:
            return {}
        stmt = (
            select(
                AttendanceEvent.employee_id,
                AttendanceEvent.fecha,
                func.min(AttendanceEvent.tiempo).label("primera_hora"),
            )
            .where(AttendanceEvent.employee_id.in_(ids))
            .where(self._report_year_filter())
            .group_by(AttendanceEvent.employee_id, AttendanceEvent.fecha)
        )
        if weeks and weeks > 0:
            today = min(date.today(), REPORT_YEAR_END)
            window_start = today - timedelta(days=weeks * 7 - 1)
            window_start = max(window_start, REPORT_YEAR_START)
            stmt = stmt.where(AttendanceEvent.fecha >= window_start)
        stmt = stmt.order_by(AttendanceEvent.employee_id, AttendanceEvent.fecha.desc())
        raw_rows = self._db.execute(stmt).all()
        if not raw_rows:
            return {employee_id: [] for employee_id in ids}
        entry_rows = [
            _SimpleEntry(
                employee_id=row.employee_id,
                fecha=row.fecha,
                primera_hora=row.primera_hora,
            )
            for row in raw_rows
        ]
        schedule_map = self._schedule_map(ids)
        schedule_map, inferred_keys = self._fill_schedule_map_with_inference(schedule_map, entry_rows)
        grouped: dict[int, dict[date, dict[int, WeeklyCheckinDay]]] = defaultdict(lambda: defaultdict(dict))
        for row in entry_rows:
            weekday = row.fecha.weekday()
            scheduled = schedule_map.get((row.employee_id, weekday))
            week_start = row.fecha - timedelta(days=weekday)
            day_entry = WeeklyCheckinDay(
                weekday=weekday,
                entrada=row.primera_hora,
                is_late=_is_late(row.primera_hora, scheduled),
                expected=scheduled,
                inferred=(row.employee_id, weekday) in inferred_keys,
            )
            grouped[row.employee_id][week_start][weekday] = day_entry

        result: dict[int, list[EmployeeWeeklyCheckin]] = {}
        for employee_id in ids:
            week_map = grouped.get(employee_id, {})
            rows: list[EmployeeWeeklyCheckin] = []
            for week_start, days_map in week_map.items():
                days: list[WeeklyCheckinDay] = []
                for weekday in range(7):
                    days.append(
                        days_map.get(
                            weekday,
                            WeeklyCheckinDay(
                                weekday=weekday,
                                entrada=None,
                                is_late=None,
                                expected=schedule_map.get((employee_id, weekday)),
                                inferred=(employee_id, weekday) in inferred_keys,
                            ),
                        )
                    )
                rows.append(
                    EmployeeWeeklyCheckin(
                        week_start=week_start,
                        week_end=week_start + timedelta(days=6),
                        days=days,
                    )
                )
            rows.sort(key=lambda item: item.week_start, reverse=True)
            result[employee_id] = rows
        return result

    def _primary_schedule_map(self, employee_ids: Iterable[int]) -> dict[int, time]:
        ids = {employee_id for employee_id in employee_ids if employee_id}
        if not ids:
            return {}
        stmt = (
            select(Schedule.employee_id, func.min(Schedule.inicio).label("inicio"))
            .where(Schedule.employee_id.in_(list(ids)))
            .group_by(Schedule.employee_id)
        )
        mapping: dict[int, time] = {}
        for employee_id, inicio in self._db.execute(stmt):
            mapping[int(employee_id)] = inicio
        self._apply_department_overrides(mapping, list(ids), primary_only=True)
        return mapping

    def _build_timeline(
        self, day: date, entries: list[ClassifiedEntry]
    ) -> list[TimelineHighlight]:
        daily_entries = [entry for entry in entries if entry.fecha == day]
        if not daily_entries:
            return [
                TimelineHighlight(
                    title="Sin eventos",
                    detail="No se registraron asistencias para la fecha consultada",
                    time="--:--",
                )
            ]
        first_entry = min(daily_entries, key=lambda entry: entry.entrada)
        late_entries = [entry for entry in daily_entries if entry.is_late]
        hour_expr = func.extract("hour", AttendanceEvent.event_ts)
        peak_stmt = (
            select(hour_expr.label("hora"), func.count().label("total"))
            .select_from(AttendanceEvent)
            .join(Employee, Employee.id == AttendanceEvent.employee_id)
            .where(AttendanceEvent.fecha == day)
            .where(_campus_filter_clause())
            .group_by(hour_expr)
            .order_by(func.count().desc())
            .limit(1)
        )
        peak_row = self._db.execute(peak_stmt).first()
        devices_stmt = (
            select(func.count(func.distinct(AttendanceEvent.device_serial)))
            .select_from(AttendanceEvent)
            .join(Employee, Employee.id == AttendanceEvent.employee_id)
            .where(AttendanceEvent.fecha == day)
            .where(_campus_filter_clause())
        )
        device_count = self._db.scalar(devices_stmt) or 0

        campus_day = defaultdict(lambda: {"on_time": 0, "late": 0})
        for entry in daily_entries:
            if entry.campus not in CAMPUS_WHITELIST:
                continue
            if entry.is_late:
                campus_day[entry.campus]["late"] += 1
            else:
                campus_day[entry.campus]["on_time"] += 1
        campus_leader = None
        for campus, stats in campus_day.items():
            total = stats["on_time"] + stats["late"]
            if total == 0:
                continue
            rate = stats["on_time"] / total
            if not campus_leader or rate > campus_leader[1]:
                campus_leader = (campus, rate)

        timeline: list[TimelineHighlight] = [
            TimelineHighlight(
                title="Primer registro",
                detail=f"{first_entry.employee_name} registró entrada en {first_entry.campus}",
                time=first_entry.entrada.strftime("%H:%M"),
            )
        ]

        if peak_row:
            peak_hour = int(peak_row.hora)
            timeline.append(
                TimelineHighlight(
                    title="Pico de entradas",
                    detail=(
                        f"{int(peak_row.total)} registros entre las {peak_hour:02d}:00 y {peak_hour:02d}:59. "
                        f"{device_count} dispositivos activos."
                    ),
                    time=f"{peak_hour:02d}:00",
                )
            )

        if campus_leader:
            leader_name, leader_rate = campus_leader
            late_total = len(late_entries)
            late_time = (
                min(late_entries, key=lambda entry: entry.entrada).entrada.strftime("%H:%M")
                if late_entries
                else "--:--"
            )
            timeline.append(
                TimelineHighlight(
                    title="Alertas de impuntualidad",
                    detail=(
                        f"{late_total} llegadas fuera de tolerancia. "
                        f"{leader_name} lidera con {leader_rate:.0%} de puntualidad."
                    ),
                    time=late_time,
                )
            )

        return timeline


def _campus_from_department(departamento: str | None) -> str:
    campus = derive_department_campus(departamento)
    if not campus:
        return "Desconocido"
    return campus if campus in CAMPUS_WHITELIST else "Otros"


def _campus_filter_clause():
    clauses = [Employee.departamento.like(f"Escuela Modelo/{campus}/%") for campus in CAMPUS_WHITELIST]
    clauses.append(Employee.campus.in_(CAMPUS_WHITELIST))
    return or_(*clauses)


def _round_to_clean_slot(value: time | None) -> time | None:
    return _round_to_nearest_slot(value)


def _round_to_nearest_slot(value: time | None) -> time | None:
    if not value:
        return value
    minutes = value.hour * 60 + value.minute + (1 if value.second >= 30 else 0)
    slot = (minutes + 15) // 30
    hour = (slot // 2) % 24
    minute = 30 if slot % 2 else 0
    return time(hour=hour, minute=minute, second=0)


def _select_expected_from_stats(stats: _ScheduleInferenceStats | None) -> time | None:
    if not stats:
        return None
    best_slot = None
    best_count = 0
    second_count = 0
    for slot, count in stats.slot_counts.items():
        if count > best_count:
            second_count = best_count
            best_slot = slot
            best_count = count
        elif count > second_count:
            second_count = count

    mean_slot = None
    if stats.samples > 0:
        mean_time = _minutes_to_time(stats.total_minutes / stats.samples)
        mean_slot = _round_to_nearest_slot(mean_time)

    if best_slot is None:
        candidate = mean_slot or _round_to_nearest_slot(stats.earliest) or stats.earliest
    else:
        divergence = best_count - second_count
        threshold = max(1, int(stats.samples * 0.15))
        if mean_slot and divergence <= threshold:
            candidate = mean_slot
        else:
            candidate = best_slot

    earliest_slot = _round_to_nearest_slot(stats.earliest)
    if earliest_slot:
        candidate_minutes = _time_to_minutes(candidate) if candidate else None
        earliest_minutes = _time_to_minutes(earliest_slot)
        if candidate_minutes is None or earliest_minutes <= candidate_minutes:
            return earliest_slot
    return candidate


def _minutes_to_time(value: float) -> time:
    total_minutes = int(round(value))
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    return time(hour=hour, minute=minute, second=0)



def _day_to_index(label: str | None) -> int | None:
    if not label:
        return None
    return DAY_TO_INDEX.get(label.strip())


def _index_to_day_label(value: int) -> str | None:
    for label, index in DAY_TO_INDEX.items():
        if index == value:
            return label
    return None


def _time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute + (1 if value.second >= 30 else 0)


def _is_late(entrada: time, scheduled: time | None) -> bool:
    if not scheduled:
        return False
    arrival = _time_to_minutes(entrada)
    target = _time_to_minutes(scheduled) + LATE_TOLERANCE_MINUTES
    return arrival > target


def _staff_daily_status(
    *,
    first_event: time | None,
    last_event: time | None,
    total_events: int,
    scheduled_start: time | None,
    scheduled_end: time | None,
) -> str:
    if first_event is None:
        return "no_events"
    if total_events == 1:
        return "absence"
    if scheduled_start is None or scheduled_end is None:
        return "no_schedule"
    if _is_late(first_event, scheduled_start):
        return "late"
    if last_event is not None and _time_to_minutes(last_event) + LATE_TOLERANCE_MINUTES < _time_to_minutes(scheduled_end):
        return "left_early"
    return "on_time"


def _schedule_bounds(intervals: Sequence[StaffScheduleInterval]) -> tuple[time | None, time | None]:
    if not intervals:
        return None, None
    return intervals[0].start, intervals[-1].end


def _merge_schedule_intervals(intervals: Sequence[tuple[time, time]]) -> list[StaffScheduleInterval]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: (_time_to_minutes(item[0]), _time_to_minutes(item[1])))
    merged: list[StaffScheduleInterval] = []
    for start_time, end_time in ordered:
        if not merged:
            merged.append(StaffScheduleInterval(start=start_time, end=end_time))
            continue
        previous = merged[-1]
        if _time_to_minutes(start_time) <= _time_to_minutes(previous.end) + SCHEDULE_CONSECUTIVE_GAP_MINUTES:
            if _time_to_minutes(end_time) > _time_to_minutes(previous.end):
                previous.end = end_time
            continue
        merged.append(StaffScheduleInterval(start=start_time, end=end_time))
    return merged


def _resolve_entry_exit_events(
    *,
    first_event: time | None,
    last_event: time | None,
    schedule_intervals: Sequence[StaffScheduleInterval],
) -> tuple[time | None, time | None, bool, bool]:
    if first_event is None and last_event is None:
        return None, None, False, False
    if first_event is not None and last_event is not None and first_event != last_event:
        return first_event, last_event, False, False

    single_event = first_event or last_event
    if single_event is None:
        return None, None, False, False

    if schedule_intervals:
        event_minutes = _time_to_minutes(single_event)
        closest_kind = "entry"
        closest_distance: int | None = None
        for interval in schedule_intervals:
            start_distance = abs(event_minutes - _time_to_minutes(interval.start))
            end_distance = abs(event_minutes - _time_to_minutes(interval.end))
            if closest_distance is None or start_distance < closest_distance:
                closest_distance = start_distance
                closest_kind = "entry"
            if closest_distance is None or end_distance < closest_distance:
                closest_distance = end_distance
                closest_kind = "exit"
        if closest_distance is not None:
            if closest_kind == "entry":
                return single_event, None, True, False
            return None, single_event, False, True

    return (single_event, None, True, False) if _time_to_minutes(single_event) < 12 * 60 else (None, single_event, False, True)


def _daterange(start_date: date, end_date: date) -> list[date]:
    total_days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(total_days + 1)]


@dataclass
class _EmployeeAccumulator:
    employee_id: int
    nombre: str
    departamento: str
    campus: str
    total_days: int = 0
    late_days: int = 0

    def add(self, is_late: bool) -> None:
        self.total_days += 1
        if is_late:
            self.late_days += 1

    def to_ranking(self) -> EmployeeRanking:
        return EmployeeRanking(
            id=self.employee_id,
            nombre=self.nombre,
            departamento=self.departamento,
            campus=self.campus,
            total_days=self.total_days,
            late_days=self.late_days,
        )


@dataclass
class _ScheduleInferenceStats:
    earliest: time | None = None
    slot_counts: dict[time, int] = field(default_factory=dict)
    total_minutes: int = 0
    samples: int = 0


@dataclass
class _SimpleEntry:
    employee_id: int
    fecha: date
    primera_hora: time
