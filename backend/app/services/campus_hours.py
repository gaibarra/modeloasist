"""Compact rectoral view; no daily detail or personal contact information."""
import csv
import io
import unicodedata
import re
from collections import defaultdict
from sqlalchemy import select
from app.models import Employee, EmployeeDepartment, Department
from app.services.weekly_hours import summarize_weekly_hours
from app.services.labor_contracts import enrich_weekly

RECTOR_REPORT_EMAILS = frozenset({"gaibarra@hotmail.com", "duchliz@modelo.edu.mx"})
REPORT_CAMPUSES = ("Chetumal", "Montejo", "Mérida", "Valladolid")


def alphabetic_key(name):
    # Spanish ordering: accents do not change position; ñ follows n.
    value = unicodedata.normalize("NFC", name).casefold().replace("ñ", "n~")
    return " ".join("".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c)).split())


def is_departed_label(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value or '') if not unicodedata.combining(c))
    value = ' '.join(re.sub(r'[/_-]+', ' ', value.upper()).split())
    return bool(re.search(r'(?:^| )(?:BAJAS(?: NOMINA)?|PASANTES|SOLUCIONES CASTRO|CONSMA CLEAN)$', value))


def report_departments(db, employee_ids, campus):
    """Exclude designated groups even if another campus assignment exists."""
    excluded, departments = set(), defaultdict(set)
    for e in db.scalars(select(Employee).where(Employee.id.in_(employee_ids))):
        if is_departed_label(e.departamento) or is_departed_label(e.campus):
            excluded.add(e.id)
    for eid, d in db.execute(select(EmployeeDepartment.employee_id, Department)
            .join(Department, Department.id == EmployeeDepartment.department_id)
            .where(EmployeeDepartment.employee_id.in_(employee_ids))):
        if any(is_departed_label(v) for v in (d.name, d.code, d.campus)):
            excluded.add(eid)
        elif d.active and d.campus == campus:
            departments[eid].add(d.name)
    return excluded, {eid: ' / '.join(sorted(names, key=alphabetic_key)) for eid, names in departments.items()}


def campus_report(db, analytics, campus, start, end):
    attendance = analytics.staff_period_attendance(period_start=start, period_end=end, campus=campus)
    summaries = enrich_weekly(db, summarize_weekly_hours(attendance), start, end, campus=campus)
    excluded, departments = report_departments(db, [r['employee_id'] for r in summaries], campus)
    rows = []
    for row, original in zip(summaries, attendance):
        if row['employee_id'] in excluded:
            continue
        notes = []
        if row["labor_contract_seconds"] is None:
            notes.append("Sin referencia contractual completa")
        if not any(day.schedule_intervals for day in original.days):
            notes.append("Sin horario registrado")
        if original.total_events == 0:
            notes.append("Sin checadas en la semana")
        if row["unmeasured_days"]:
            notes.append(f"{row['unmeasured_days']} días programados sin tiempo calculable")
        if row["incomplete_days"]:
            notes.append(f"{row['incomplete_days']} días con marcas incompletas")
        if row["credited_seconds"]:
            notes.append(f"{hours(row['credited_seconds'])} h acreditadas por justificación según horario")
        if row["justified_days"]:
            notes.append(f"{row['justified_days']} días justificados")
        rows.append({key: row[key] for key in (
            "employee_id", "employee_name", "labor_contract_seconds", "scheduled_seconds", "worked_seconds",
            "scheduled_contract_difference_seconds", "worked_scheduled_difference_seconds",
        )} | {"observations": "; ".join(notes) or "—",
              "department_name": departments.get(row['employee_id'], 'Sin departamento')})
    rows.sort(key=lambda row: (alphabetic_key(row["employee_name"]), row["employee_id"]))
    all_contracts = all(r["labor_contract_seconds"] is not None for r in rows)
    return {"campus": campus, "start_date": start, "end_date": end, "rows": rows,
            "totals": {"employees": len(rows), "labor_contract_seconds": sum(r["labor_contract_seconds"] for r in rows) if all_contracts else None,
                       "scheduled_seconds": sum(r["scheduled_seconds"] for r in rows), "worked_seconds": sum(r["worked_seconds"] for r in rows)}}


def hours(value):
    if value is None:
        return "Sin referencia completa"
    minutes = round(abs(value) / 60)
    return f"{'−' if value < 0 else ''}{minutes // 60}:{minutes % 60:02}"


def report_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Campus", "Semana inicial", "Semana final", "Colaborador", "Departamento", "Contrato laboral (h:mm)", "Programadas (h:mm)", "Trabajadas estimadas (h:mm)", "Programadas - contrato", "Trabajadas - programadas", "Observaciones"])
    for row in report["rows"]:
        name = row["employee_name"]
        if name.lstrip().startswith(("=", "+", "-", "@")):
            name = "'" + name
        department = row['department_name']
        if department.lstrip().startswith(('=', '+', '-', '@')):
            department = "'" + department
        writer.writerow([report["campus"], report["start_date"], report["end_date"], name, department,
                         *[hours(row[key]) for key in ("labor_contract_seconds", "scheduled_seconds", "worked_seconds", "scheduled_contract_difference_seconds", "worked_scheduled_difference_seconds")], row["observations"]])
    return "\ufeff" + output.getvalue()
