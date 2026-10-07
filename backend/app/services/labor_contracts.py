"""Read-only reconciliation. Contracts never replace schedule or attendance data."""
from collections import defaultdict
from datetime import date
from sqlalchemy import select, inspect
from sqlalchemy.orm import selectinload
from app.models import LaborContract, LaborContractImport, StaffSemesterSchedule, Employee, EmployeeDepartment, Department

LABELS = {"matches": "Coincide", "lower": "Horario inferior", "higher": "Horario superior",
          "no_schedule": "Sin horario", "pending_contract": "Contrato pendiente", "pending_identity": "Identidad pendiente"}


def available(db):
    return inspect(db.connection()).has_table("labor_contracts") and inspect(db.connection()).has_table("labor_contract_imports")


def merged_minutes(blocks):
    merged = []
    for start, end in sorted(set(blocks)):
        if end <= start:
            raise ValueError("Horario inválido: final anterior al inicio")
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(b - a for a, b in merged)


def semester_minutes(schedule):
    if schedule is None:
        return None
    days = defaultdict(list)
    for block in schedule.intervals:
        days[block.weekday].append((block.start.hour * 60 + block.start.minute, block.end.hour * 60 + block.end.minute))
    return sum(merged_minutes(blocks) for blocks in days.values())


def covering_contract(contracts, start, end):
    matches = [c for c in contracts if c.active and c.valid_from <= start and c.valid_until >= end]
    return matches[0] if len(matches) == 1 else None


def comparison(contract_minutes, scheduled_minutes):
    if contract_minutes is None:
        return "pending_contract"
    if scheduled_minutes is None:
        return "no_schedule"
    return "matches" if scheduled_minutes == contract_minutes else "lower" if scheduled_minutes < contract_minutes else "higher"


def reconciliation(db, department_ids, year=2026, semester=2, employee_id=None):
    start, end = date(year, 1 if semester == 1 else 8, 1), date(year, 6 if semester == 1 else 12, 30 if semester == 1 else 31)
    query = select(Employee, Department).join(EmployeeDepartment, EmployeeDepartment.employee_id == Employee.id).join(Department, Department.id == EmployeeDepartment.department_id).where(Department.id.in_(department_ids))
    if employee_id is not None:
        query = query.where(Employee.id == employee_id)
    people = db.execute(query.order_by(Employee.nombre, Department.name)).all()
    ids = {e.id for e, _ in people}
    schedules = {s.employee_id: s for s in db.scalars(select(StaffSemesterSchedule).options(selectinload(StaffSemesterSchedule.intervals)).where(StaffSemesterSchedule.employee_id.in_(ids), StaffSemesterSchedule.academic_year == year, StaffSemesterSchedule.semester == semester))}
    contract_map = defaultdict(list)
    seen, pending = set(), set()
    ready = available(db)
    if ready:
        for c in db.scalars(select(LaborContract).where(LaborContract.employee_id.in_(ids), LaborContract.active.is_(True))):
            contract_map[c.employee_id].append(c)
        latest = db.scalar(select(LaborContractImport).where(LaborContractImport.reverted_at.is_(None)).order_by(LaborContractImport.id.desc()))
        if latest:
            for r in latest.audit.get("source_rows", []):
                if r.get("employee_id"):
                    seen.add(r["employee_id"])
                pending.update(r.get("candidate_ids", []))
    rows = []
    for employee, department in people:
        contract = covering_contract(contract_map[employee.id], start, end)
        minutes = contract.weekly_minutes if contract else None
        scheduled = semester_minutes(schedules.get(employee.id))
        status = comparison(minutes, scheduled)
        if employee.id in pending and employee.id not in seen:
            status = "pending_identity"
        rows.append(dict(employee_id=employee.id, employee_name=employee.nombre, department_id=department.id,
                         department_name=department.name, campus=department.campus,
                         contract_minutes=minutes, scheduled_minutes=scheduled,
                         difference_minutes=scheduled - minutes if scheduled is not None and minutes is not None else None,
                         status=status, status_label=LABELS[status],
                         source_presence="En archivo" if employee.id in seen else "Identidad pendiente" if employee.id in pending else "Sin información en este archivo"))
    return {"available": ready, "academic_year": year, "semester": semester, "rows": rows}


def enrich_weekly(db, rows, start, end):
    contract_map = defaultdict(list)
    if available(db):
        for contract in db.scalars(select(LaborContract).where(LaborContract.employee_id.in_([r["employee_id"] for r in rows]), LaborContract.active.is_(True))):
            contract_map[contract.employee_id].append(contract)
    for row in rows:
        contract = covering_contract(contract_map[row["employee_id"]], start, end)
        seconds = contract.weekly_minutes * 60 if contract else None
        # Keep legacy keys for API consumers; their meaning remains scheduled time.
        row.update(labor_contract_seconds=seconds, scheduled_seconds=row["contracted_seconds"],
                   scheduled_contract_difference_seconds=row["contracted_seconds"] - seconds if seconds is not None else None,
                   worked_scheduled_difference_seconds=row["difference_seconds"])
    return rows
