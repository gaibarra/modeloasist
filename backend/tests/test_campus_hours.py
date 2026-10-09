from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from tests.test_labor_contracts import db  # noqa: F401 — isolated database fixture
from app.main import app
from app.db.session import get_db
from app.dependencies.auth import AuthenticatedActor, get_current_actor
from app.models import Department, Employee, EmployeeDepartment, StaffUser
from app.services.analytics import AnalyticsService
from app.services.campus_hours import alphabetic_key, campus_report, report_csv

START, END = date(2026, 10, 5), date(2026, 10, 11)
QUERY = {"campus": "Mérida", "start_date": str(START), "end_date": str(END)}


@pytest.fixture
def client(db):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def authorize(db, email, active=True, role="staff"):
    staff = db.get(StaffUser, 10)
    staff.email, staff.is_active = email, active
    actor = AuthenticatedActor(actor_type=role, is_admin=False, must_change_password=False,
                               staff=staff if role == "staff" else None, department_ids=set())
    app.dependency_overrides[get_current_actor] = lambda: actor


@pytest.mark.parametrize("email", ["gaibarra@hotmail.com", "duchliz@modelo.edu.mx", "GAIBARRA@HOTMAIL.COM"])
def test_authorized_report_and_export_without_department_scope(db, client, email):
    authorize(db, email)
    result = client.get("/staff/campus-hours", params=QUERY)
    assert result.status_code == 200
    row = result.json()["rows"][0]
    assert row["employee_id"] == 1
    assert row["worked_seconds"] == 0
    assert row["labor_contract_seconds"] is None
    assert "Sin checadas" in row["observations"]
    assert "days" not in row and "employee_email" not in row
    csv = client.get("/staff/campus-hours", params=QUERY | {"export": True})
    assert csv.status_code == 200
    assert "text/csv" in csv.headers["content-type"]
    assert "no-store" in csv.headers["cache-control"]


@pytest.mark.parametrize("email,active,role", [
    ("other@example.com", True, "staff"),
    ("gaibarra@hotmail.com", False, "staff"),
    ("gaibarra@hotmail.com", True, "employee"),
])
def test_denied_including_other_superadmins_and_csv(db, client, email, active, role):
    authorize(db, email, active, role)
    for export in (False, True):
        assert client.get("/staff/campus-hours", params=QUERY | {"export": export}).status_code == 403


def test_anonymous_denied(client):
    assert client.get("/staff/campus-hours", params=QUERY).status_code == 401


@pytest.mark.parametrize("changes", [{"campus": "BAJAS"}, {"start_date": "2026-10-06"},
                                     {"end_date": "2026-10-18"}, {"end_date": "2026-10-04"}])
def test_invalid_campus_or_week(db, client, changes):
    authorize(db, "gaibarra@hotmail.com")
    assert client.get("/staff/campus-hours", params=QUERY | changes).status_code == 400


def test_campus_deduplicates_and_includes_no_events_in_alphabetical_order(db):
    db.add_all([
        Department(id=5, name="Extra", code="Extra", campus="Mérida"),
        Department(id=6, name="Inactive", code="Inactive", campus="Mérida", active=False),
        EmployeeDepartment(employee_id=1, department_id=5, is_primary=False),
        Employee(id=3, nombre="ÁLVAREZ ANA", email="ana@example.test", departamento="CME-DTI"),
        EmployeeDepartment(employee_id=3, department_id=3, is_primary=True),
        EmployeeDepartment(employee_id=2, department_id=6, is_primary=False),
    ])
    db.commit()
    report = campus_report(db, AnalyticsService(db), "Mérida", START, END)
    assert [r["employee_id"] for r in report["rows"]] == [3, 1]
    assert report["totals"]["employees"] == 2
    assert report["totals"]["labor_contract_seconds"] is None
    assert "pendiente.local" not in report_csv(report)
    report["rows"][0]["employee_name"] = "=BAD()"
    assert "'=BAD()" in report_csv(report)


def test_spanish_sort():
    assert sorted(["ÑU", "ÓSCAR", "NUBE", "ÁLVAREZ"], key=alphabetic_key) == ["ÁLVAREZ", "NUBE", "ÑU", "ÓSCAR"]


def test_three_figures_are_independent(db, monkeypatch):
    from tests.test_weekly_hours import summarize
    from app.services import campus_hours
    row = summarize()
    def enrich(_db, rows, start, end):
        assert (start, end) == (START, END)
        return [row | {"labor_contract_seconds": 40 * 3600, "scheduled_seconds": 8 * 3600,
                       "scheduled_contract_difference_seconds": -32 * 3600,
                       "worked_scheduled_difference_seconds": 0}]
    monkeypatch.setattr(campus_hours, "summarize_weekly_hours", lambda _: [row])
    monkeypatch.setattr(campus_hours, "enrich_weekly", enrich)
    analytics = SimpleNamespace(staff_period_attendance=lambda **_: [SimpleNamespace(
        total_events=2, days=[SimpleNamespace(schedule_intervals=[1])])])
    report = campus_report(db, analytics, "Mérida", START, END)
    result = report["rows"][0]
    assert result["labor_contract_seconds"] == 144000
    assert result["scheduled_seconds"] == result["worked_seconds"] == 28800


def test_justified_hours_follow_date_override_in_weekly_campus_and_csv(db, client):
    from datetime import datetime, time
    from app.models.staff_schedule import StaffSemesterSchedule, StaffSemesterScheduleInterval
    from app.models.staff_schedule_override import StaffScheduleDateOverride, StaffScheduleDateOverrideInterval
    from app.models.staff_attendance_exemption import StaffAttendanceExemption

    base = StaffSemesterSchedule(employee_id=1, academic_year=2026, semester=2)
    base.intervals = [StaffSemesterScheduleInterval(weekday=3, start=time(7), end=time(15))]
    target = date(2026, 10, 8)
    override = StaffScheduleDateOverride(employee_id=1, target_date=target)
    override.intervals = [StaffScheduleDateOverrideInterval(position=0, start=time(9), end=time(12)),
                          StaffScheduleDateOverrideInterval(position=1, start=time(13), end=time(16))]
    exemption = StaffAttendanceExemption(employee_id=1, department_id=3, target_date=target,
                                          exempt_entry=True, exempt_exit=True, reason="fuerza_mayor")
    db.add_all([base, override, exemption])
    db.commit()
    authorize(db, "gaibarra@hotmail.com")
    campus = client.get('/staff/campus-hours', params=QUERY).json()
    assert campus['rows'][0]['worked_seconds'] == campus['totals']['worked_seconds'] == 6 * 3600
    assert '6:00 h acreditadas' in campus['rows'][0]['observations']
    csv = client.get('/staff/campus-hours', params=QUERY | {'export': True})
    assert '6:00 h acreditadas' in csv.text
    weekly = client.get('/staff/weekly-hours', params={'department_id': 3, 'start_date': str(START), 'end_date': str(END)})
    assert weekly.status_code == 200
    row = weekly.json()['rows'][0]
    assert row['worked_seconds'] == row['credited_seconds'] == 6 * 3600
    assert row['unmeasured_days'] == 0
    day = next(d for d in row['days'] if d['date'] == str(target))
    assert day['credited_seconds'] == 6 * 3600
    assert day['total_events'] == 0 and day['first_event'] is None
    exemption.revoked_at = datetime(2026, 10, 9, 12)
    db.commit()
    campus = client.get('/staff/campus-hours', params=QUERY).json()
    assert campus['rows'][0]['worked_seconds'] == 0
    assert 'acreditadas' not in campus['rows'][0]['observations']
