"""Read-only weekly comparison using the historical, effective daily schedule.

Biometric events have no entry/exit direction. Worked time is consequently an
estimate between the first and last distinct marks, excluding scheduled breaks.
Fully justified days without sufficient marks receive their effective scheduled
hours. Fully justified force-majeure days also top up a short observed shift to
the scheduled duration. Only the credited supplement is reported separately.
"""
from app.schemas.staff import StaffMobilePeriodRow


def _seconds(value):
    return value.hour * 3600 + value.minute * 60 + value.second


def summarize_weekly_hours(rows: list[StaffMobilePeriodRow]) -> list[dict]:
    result = []
    for row in rows:
        days = []
        for day in row.days:
            # Merge overlapping/duplicate blocks without double-counting time.
            intervals = []
            for block in sorted(day.schedule_intervals, key=lambda item: item.start):
                start, end = _seconds(block.start), _seconds(block.end)
                if end <= start:
                    continue
                if intervals and start <= intervals[-1][1]:
                    intervals[-1][1] = max(intervals[-1][1], end)
                else:
                    intervals.append([start, end])
            rest = day.is_official_holiday and not day.holiday_work_authorized
            contracted = 0 if rest else sum(end - start for start, end in intervals)
            complete = (day.total_events >= 2 and day.first_event is not None
                        and day.last_event is not None and day.last_event > day.first_event)
            worked = None
            if complete:
                first, last = _seconds(day.first_event), _seconds(day.last_event)
                breaks = sum(max(0, min(last, right[0]) - max(first, left[1]))
                             for left, right in zip(intervals, intervals[1:]))
                worked = max(0, last - first - breaks)
            full_exemption = day.exempt_entry and day.exempt_exit
            credit_schedule = full_exemption and (
                not complete or day.exemption_reason == "fuerza_mayor"
            )
            credited = max(0, contracted - (worked or 0)) if credit_schedule else 0
            if credited:
                worked = (worked or 0) + credited
            days.append({
                "date": day.date,
                "contracted_seconds": contracted,
                "worked_seconds": worked,
                "credited_seconds": credited,
                "total_events": day.total_events,
                "justified": day.exempt_entry or day.exempt_exit,
                "exemption_reason": day.exemption_reason,
                "official_holiday": day.official_holiday_name if rest else None,
                "incomplete": day.total_events > 0 and not complete and not credited,
                "schedule": day.schedule_intervals,
                "first_event": day.first_event,
                "last_event": day.last_event,
            })
        contracted = sum(day["contracted_seconds"] for day in days)
        worked = sum(day["worked_seconds"] or 0 for day in days)
        result.append({
            "employee_id": row.employee_id,
            "employee_name": row.employee_name,
            "contracted_seconds": contracted,
            "worked_seconds": worked,
            "credited_seconds": sum(day["credited_seconds"] for day in days),
            "difference_seconds": worked - contracted,
            "justified_days": sum(day["justified"] for day in days),
            "incomplete_days": sum(day["incomplete"] for day in days),
            "unmeasured_days": sum(day["contracted_seconds"] > 0 and day["worked_seconds"] is None for day in days),
            "days": days,
        })
    return result
