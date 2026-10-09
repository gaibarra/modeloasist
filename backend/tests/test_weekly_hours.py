from datetime import date, time

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models.employee import Employee
from app.models.staff_access import EmployeeDepartment
from app.models.staff_schedule import StaffSemesterSchedule, StaffSemesterScheduleInterval
from app.models.staff_schedule_override import StaffScheduleDateOverride, StaffScheduleDateOverrideInterval
from app.schemas.staff import StaffMobilePeriodDay, StaffMobilePeriodRow, StaffScheduleInterval
from app.services.weekly_hours import summarize_weekly_hours
from tests.test_staff_mobile import seed_staff_mobile_data, auth_headers
from tests.conftest import TestingSessionLocal


def summarize(**kwargs):
    day = StaffMobilePeriodDay(
        date=date(2026, 10, 5), status="on_time",
        **({"total_events": 2, "first_event": time(7), "last_event": time(15),
            "schedule_intervals": [StaffScheduleInterval(start=time(7), end=time(15))]} | kwargs),
    )
    row = StaffMobilePeriodRow(employee_id=1, employee_name="Ana", department_id=3,
                              department_name="Dept", total_events=day.total_events,
                              active_days=int(day.total_events > 0), period_start=day.date,
                              period_end=day.date, days=[day])
    return summarize_weekly_hours([row])[0]


def test_complete_shift_and_difference():
    row = summarize(first_event=time(8))
    assert row["contracted_seconds"] == 8 * 3600
    assert row["worked_seconds"] == 7 * 3600
    assert row["difference_seconds"] == -3600


def test_split_shift_excludes_only_break_within_observed_span():
    blocks = [StaffScheduleInterval(start=time(7), end=time(12)), StaffScheduleInterval(start=time(13), end=time(16))]
    assert summarize(schedule_intervals=blocks, last_event=time(16))["worked_seconds"] == 8 * 3600
    assert summarize(schedule_intervals=blocks, last_event=time(12, 30))["worked_seconds"] == 5 * 3600


def test_duplicate_or_overlapping_schedule_blocks_do_not_double_count():
    blocks = [StaffScheduleInterval(start=time(7), end=time(15))] * 2
    assert summarize(schedule_intervals=blocks)["contracted_seconds"] == 8 * 3600


@pytest.mark.parametrize("events,last", [(0, None), (1, time(7)), (2, time(7))])
def test_no_fabricated_time_from_missing_or_identical_marks(events, last):
    row = summarize(total_events=events, last_event=last)
    assert row["days"][0]["worked_seconds"] is None
    assert row["worked_seconds"] == 0
    assert row["unmeasured_days"] == 1


def test_home_office_credits_effective_schedule_without_marks():
    row = summarize(total_events=0, first_event=None, last_event=None,
                    exempt_entry=True, exempt_exit=True, exemption_reason="home_office")
    assert row["justified_days"] == 1
    assert row["contracted_seconds"] == 8 * 3600
    assert row["worked_seconds"] == 8 * 3600
    assert row["credited_seconds"] == 8 * 3600
    assert row["unmeasured_days"] == 0


def test_holiday_and_authorized_shift():
    assert summarize(is_official_holiday=True)["contracted_seconds"] == 0
    assert summarize(is_official_holiday=True, holiday_work_authorized=True)["contracted_seconds"] == 8 * 3600


def test_events_without_schedule_are_still_counted():
    row = summarize(schedule_intervals=[])
    assert row["worked_seconds"] == 8 * 3600
    assert row["contracted_seconds"] == 0


def test_weekly_hours_api_scope_range_and_employee_access():
    seed_staff_mobile_data()
    with TestClient(app) as client:
        headers = auth_headers(client)
        query = {"department_id": 3, "start_date": "2026-03-23", "end_date": "2026-03-29"}
        response = client.get("/staff/weekly-hours", params=query, headers=headers)
        assert response.status_code == 200
        assert len(response.json()["rows"]) == 1
        assert len(response.json()["rows"][0]["days"]) == 7
        assert client.get("/staff/weekly-hours", params=query | {"department_id": 4}, headers=headers).status_code == 403
        assert client.get("/staff/weekly-hours", params=query | {"end_date": "2026-04-05"}, headers=headers).status_code == 400
        assert client.get("/staff/weekly-hours", params=query | {"start_date": "2026-03-24"}, headers=headers).status_code == 400
        assert client.get("/staff/weekly-hours", params=query).status_code == 401
        token = client.post("/auth/login", json={"email": "ana@example.com", "password": "modelo2026"}).json()["access_token"]
        assert client.get("/staff/weekly-hours", params=query, headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_api_includes_unrecorded_employees_and_effective_override_without_writes():
    seed_staff_mobile_data()
    with TestingSessionLocal() as db:
        db.add(Employee(id=2, nombre="Zulema Sin Marcas", departamento="Escuela Modelo/Montejo/MTJ-Contabilidad", email="zulema@example.com"))
        db.add(EmployeeDepartment(employee_id=2, department_id=3, is_primary=True))
        base = StaffSemesterSchedule(employee_id=2, academic_year=2026, semester=1)
        base.intervals = [StaffSemesterScheduleInterval(weekday=0, start=time(7), end=time(15))]
        override = StaffScheduleDateOverride(employee_id=2, target_date=date(2026, 3, 23))
        override.intervals = [StaffScheduleDateOverrideInterval(position=0, start=time(9), end=time(15))]
        db.add_all([base, override])
        db.commit()
    with TestClient(app) as client:
        response = client.get("/staff/weekly-hours", headers=auth_headers(client), params={
            "department_id": 3, "start_date": "2026-03-23", "end_date": "2026-03-29",
        })
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert [row["employee_id"] for row in rows] == [1, 2]
        assert rows[1]["contracted_seconds"] == 6 * 3600
        assert rows[1]["worked_seconds"] == 0
        assert rows[1]["unmeasured_days"] == 1
    with TestingSessionLocal() as db:
        assert db.query(StaffSemesterScheduleInterval).one().start == time(7)
        assert db.query(StaffScheduleDateOverrideInterval).one().start == time(9)


@pytest.mark.parametrize("events,last", [(0, None), (1, time(7)), (2, time(7))])
def test_fully_justified_missing_marks_credit_split_shift_once(events, last):
    blocks = [StaffScheduleInterval(start=time(7), end=time(12)),
              StaffScheduleInterval(start=time(13), end=time(16)),
              StaffScheduleInterval(start=time(7), end=time(12))]
    row = summarize(total_events=events, last_event=last, schedule_intervals=blocks,
                    exempt_entry=True, exempt_exit=True, exemption_reason="fuerza_mayor")
    assert row["worked_seconds"] == row["contracted_seconds"] == 8 * 3600
    assert row["difference_seconds"] == 0
    assert row["credited_seconds"] == 8 * 3600
    assert row["unmeasured_days"] == row["incomplete_days"] == 0


def test_justification_with_complete_marks_does_not_double_count():
    row = summarize(first_event=time(8), exempt_entry=True, exempt_exit=True)
    assert row["worked_seconds"] == 7 * 3600
    assert row["credited_seconds"] == 0


@pytest.mark.parametrize("flags", [{"exempt_entry": True}, {"exempt_exit": True}])
def test_partial_justification_does_not_credit_full_day(flags):
    row = summarize(total_events=0, first_event=None, last_event=None, **flags)
    assert row["worked_seconds"] == row["credited_seconds"] == 0
    assert row["unmeasured_days"] == 1


def test_full_justification_needs_effective_working_schedule():
    row = summarize(total_events=0, first_event=None, last_event=None,
                    exempt_entry=True, exempt_exit=True, schedule_intervals=[])
    assert row["worked_seconds"] == row["credited_seconds"] == 0
    row = summarize(total_events=0, first_event=None, last_event=None,
                    exempt_entry=True, exempt_exit=True, is_official_holiday=True)
    assert row["worked_seconds"] == row["credited_seconds"] == 0
    row = summarize(total_events=0, first_event=None, last_event=None,
                    exempt_entry=True, exempt_exit=True, is_official_holiday=True,
                    holiday_work_authorized=True)
    assert row["worked_seconds"] == row["credited_seconds"] == 8 * 3600


@pytest.mark.parametrize("reason,expected,credited", [
    ("fuerza_mayor", 8 * 3600, 5 * 3600 + 11 * 60),
    ("home_office", 2 * 3600 + 49 * 60, 0),
])
def test_short_emergency_visit_on_force_majeure_day(reason, expected, credited):
    row = summarize(first_event=time(9, 35), last_event=time(12, 24),
                    exempt_entry=True, exempt_exit=True, exemption_reason=reason)
    assert row["worked_seconds"] == expected
    assert row["credited_seconds"] == credited
    assert row["days"][0]["first_event"] == time(9, 35)
    assert row["days"][0]["last_event"] == time(12, 24)


def test_force_majeure_does_not_duplicate_or_reduce_long_observed_shift():
    row = summarize(first_event=time(7), last_event=time(16),
                    exempt_entry=True, exempt_exit=True, exemption_reason="fuerza_mayor")
    assert row["worked_seconds"] == 9 * 3600
    assert row["credited_seconds"] == 0


def test_partial_force_majeure_does_not_credit_full_day():
    row = summarize(first_event=time(9, 35), last_event=time(12, 24),
                    exempt_entry=True, exemption_reason="fuerza_mayor")
    assert row["worked_seconds"] == 2 * 3600 + 49 * 60
    assert row["credited_seconds"] == 0
