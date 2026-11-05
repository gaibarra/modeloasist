"""Read-only reconciliation. Contracts never replace schedule or attendance data."""
from collections import defaultdict
from datetime import date
from sqlalchemy import select, inspect
from sqlalchemy.orm import selectinload
from app.models import LaborContract, LaborContractImport, StaffSemesterSchedule, Employee, EmployeeDepartment, Department
from app.models import CampusLaborContract

CAMPUS_CODES = {'Mérida': 'CME', 'Valladolid': 'CVA', 'Chetumal': 'CCH', 'Montejo': 'MTJ'}


def campus_contract_map(db, ids):
    result = defaultdict(list)
    if inspect(db.connection()).has_table('campus_labor_contracts'):
        for c in db.scalars(select(CampusLaborContract).where(CampusLaborContract.employee_id.in_(ids), CampusLaborContract.active.is_(True))):
            result[c.employee_id].append(c)
    return result

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


def covering_contract(contracts, start, end, campus=None):
    code = CAMPUS_CODES.get(campus, campus)
    scoped = [c for c in contracts if getattr(c, 'campus_code', None) == code and code is not None
              and c.active and c.valid_from <= end and c.valid_until >= start]
    # A partial week or explicit pending contract must not fall back to legacy.
    pool = scoped if scoped else [c for c in contracts if not getattr(c, 'campus_code', None)]
    matches = [c for c in pool if c.active and c.valid_from <= start and c.valid_until >= end]
    return matches[0] if len(matches) == 1 else None


def comparison(contract_minutes, scheduled_minutes):
    if contract_minutes is None:
        return "pending_contract"
    if scheduled_minutes is None:
        return "no_schedule"
    return "matches" if scheduled_minutes == contract_minutes else "lower" if scheduled_minutes < contract_minutes else "higher"


def reconciliation(db, department_ids, year=2026, semester=2, employee_id=None):
    from app.services.report_eligibility import report_employee_clause
    start, end = date(year, 1 if semester == 1 else 8, 1), date(year, 6 if semester == 1 else 12, 30 if semester == 1 else 31)
    query = select(Employee, Department).join(EmployeeDepartment, EmployeeDepartment.employee_id == Employee.id).join(Department, Department.id == EmployeeDepartment.department_id).where(Department.id.in_(department_ids))
    if employee_id is not None:
        query = query.where(Employee.id == employee_id)
    people = db.execute(query.where(report_employee_clause(db)).order_by(Employee.nombre, Department.name)).all()
    ids = {e.id for e, _ in people}
    schedules = {s.employee_id: s for s in db.scalars(select(StaffSemesterSchedule).options(selectinload(StaffSemesterSchedule.intervals)).where(StaffSemesterSchedule.employee_id.in_(ids), StaffSemesterSchedule.academic_year == year, StaffSemesterSchedule.semester == semester))}
    contract_map = defaultdict(list)
    presence = {}
    ready = available(db)
    if ready:
        for c in db.scalars(select(LaborContract).where(LaborContract.employee_id.in_(ids), LaborContract.active.is_(True))):
            contract_map[c.employee_id].append(c)
        receipts = list(db.scalars(select(LaborContractImport).where(LaborContractImport.reverted_at.is_(None)).order_by(LaborContractImport.id.desc())))
        for campus in {d.campus for _, d in people}:
            seen, pending = set(), set()
            latest = next((r for r in receipts if 'source_rows' in r.audit and
                (not r.audit.get('campus_code') or r.audit['campus_code'] == CAMPUS_CODES.get(campus))), None)
            if latest:
                for r in latest.audit.get('source_rows', []):
                    if r.get('employee_id') and not r.get('errors'): seen.add(r['employee_id'])
                    pending.update(r.get('candidate_ids', []))
            presence[campus] = (seen, pending)
    scoped_contracts = campus_contract_map(db, ids)
    rows = []
    for employee, department in people:
        seen, pending = presence.get(department.campus, (set(), set()))
        contract = covering_contract(contract_map[employee.id] + scoped_contracts[employee.id], start, end, department.campus)
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


def enrich_weekly(db, rows, start, end, campus=None):
    contract_map = defaultdict(list)
    if available(db):
        for contract in db.scalars(select(LaborContract).where(LaborContract.employee_id.in_([r["employee_id"] for r in rows]), LaborContract.active.is_(True))):
            contract_map[contract.employee_id].append(contract)
    scoped_contracts = campus_contract_map(db, [r['employee_id'] for r in rows])
    for row in rows:
        contract = covering_contract(contract_map[row["employee_id"]] + scoped_contracts[row['employee_id']], start, end, campus)
        seconds = contract.weekly_minutes * 60 if contract and contract.weekly_minutes is not None else None
        # Keep legacy keys for API consumers; their meaning remains scheduled time.
        row.update(labor_contract_seconds=seconds, scheduled_seconds=row["contracted_seconds"],
                   scheduled_contract_difference_seconds=row["contracted_seconds"] - seconds if seconds is not None else None,
                   worked_scheduled_difference_seconds=row["difference_seconds"])
    return rows
