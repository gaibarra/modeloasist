"""CME-only, two-phase, versioned contract import. No employee/profile mutations."""
import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re

from openpyxl import load_workbook, Workbook
from sqlalchemy import select, inspect, text
from app.models import Employee, EmployeeDepartment, Department, StaffUser, CampusLaborContract, LaborContractImport
from app.services.semester_file_import import compact_name
from app.services.labor_contract_import import digest, state_digest, backup_database
from app.services.labor_contracts import covering_contract, campus_contract_map

START, END = date(2026, 8, 1), date(2026, 12, 31)


def cme_employee_ids(db):
    return {eid for eid, code in db.execute(select(EmployeeDepartment.employee_id, Department.code)
        .join(Department, Department.id == EmployeeDepartment.department_id).where(Department.active.is_(True)))
        if re.search(r'(^|-)CME-', code)}


def distance(a, b):
    if abs(len(a)-len(b)) > 2: return 3
    previous = list(range(len(b)+1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j]+1, current[-1]+1, previous[j-1]+(ca != cb)))
        if min(current) > 2: return 3
        previous = current
    return previous[-1]


def minutes(value):
    if value is None: return None
    try:
        n = Decimal(str(value)) * 60
        if not n.is_finite() or n < 0 or n > 10080 or n != n.to_integral_value(): raise ValueError()
        return int(n)
    except (InvalidOperation, ValueError):
        raise ValueError('Horas inválidas; se requieren minutos exactos, no redondeos')


def read_source(path):
    book = load_workbook(path, read_only=True, data_only=True)
    rows = []
    try:
        if len(book.sheetnames) != 1: raise ValueError('Se esperaba una sola hoja')
        sheet = book.active
        values = sheet.iter_rows(values_only=True)
        if tuple(next(values)) != ('CLAVE','NOMBRE COMPLETO','DEPARTAMENTO','NOMBRE DEL DEPTO','HORAS CONTRATO','NOMBRE DEL PUESTO'):
            raise ValueError('Encabezados inesperados')
        for number, data in enumerate(values, 2):
            if not any(v is not None for v in data): continue
            errors = []
            try: value = minutes(data[4])
            except ValueError as exc: value = None; errors.append(str(exc))
            if not data[0] or not data[1]: errors.append('Falta clave o nombre')
            rows.append(dict(key=f'{sheet.title}:{number}', sheet=sheet.title, row=number,
                source_employee_key=str(data[0] or ''), source_name=str(data[1] or '').strip(),
                department_code=str(data[2] or ''), department_name=str(data[3] or '').strip(),
                weekly_minutes=value, job_title=str(data[5] or '').strip(), errors=errors))
    finally: book.close()
    counts = Counter(r['source_employee_key'] for r in rows)
    for r in rows:
        if counts[r['source_employee_key']] > 1: r['errors'].append('Clave duplicada en archivo')
    return rows


def preview(db, path):
    rows = read_source(path)
    people = list(db.scalars(select(Employee).order_by(Employee.id)))
    names, external = defaultdict(list), defaultdict(list)
    for e in people:
        names[compact_name(e.nombre)].append(e)
        if e.external_employee_id is not None: external[str(e.external_employee_id)].append(e)
    scope = cme_employee_ids(db)
    for r in rows:
        key = compact_name(r['source_name'])
        candidates = names.get(key, [])
        criterion = 'Nombre normalizado'
        if not candidates and len(key) >= 12:
            candidates = [e for n, group in names.items() if distance(key, n) <= 2 for e in group]
            criterion = 'Hasta 2 caracteres de diferencia'
        corroboration = external.get(r['source_employee_key'], [])
        if len(candidates) > 1 and len(corroboration) == 1 and corroboration[0] in candidates:
            candidates = corroboration
            criterion += ' + clave de checador corroborada'
        r.update(employee_id=None, application_name=None, candidate_ids=[e.id for e in candidates], criterion=criterion)
        if len(candidates) != 1:
            r['errors'].append('Identidad ambigua' if candidates else 'Sin candidato seguro')
            continue
        e = candidates[0]
        r.update(employee_id=e.id, application_name=e.nombre)
        if e.id not in scope: r['errors'].append('Sin asignación activa CME; no se cambian asignaciones')
        if corroboration and any(c.id != e.id for c in corroboration): r['errors'].append('Clave de checador apunta a otra persona')
    matched = Counter(r['employee_id'] for r in rows if r['employee_id'])
    for r in rows:
        if r['employee_id'] and matched[r['employee_id']] > 1: r['errors'].append('Varias filas para la misma persona')
        r['eligible'] = not r['errors']
    scoped = campus_contract_map(db, [e.id for e in people])
    contracts = [{k:getattr(c,k) for k in ('id','employee_id','campus_code','valid_from','valid_until','weekly_minutes','job_title','department_code','department_name','active','import_id')}
                 for cs in scoped.values() for c in cs]
    return dict(source_name=Path(path).name, source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        campus_code='CME', valid_from=str(START), valid_until=str(END),
        state=digest([state_digest(db), contracts, sorted(scope), [(e.id,e.external_employee_id) for e in people]]),
        rows=rows, summary=dict(rows=len(rows), eligible=sum(r['eligible'] for r in rows),
            pending=sum(not r['eligible'] for r in rows), pending_hours=sum(r['weekly_minutes'] is None and r['eligible'] for r in rows)))


def snapshot(c):
    return {k: str(getattr(c,k)) if k in ('valid_from','valid_until') else getattr(c,k)
            for k in ('id','employee_id','campus_code','valid_from','valid_until','weekly_minutes','job_title','department_code','department_name','source_employee_key','source_sheet','source_row','import_id','active')}


def replace_contract(db, employee_id, data, receipt_id, expected_id):
    # Lock the employee to serialize even when no contract exists yet.
    db.execute(select(Employee.id).where(Employee.id==employee_id).with_for_update()).one()
    current = list(db.scalars(select(CampusLaborContract).where(CampusLaborContract.employee_id==employee_id,
        CampusLaborContract.campus_code=='CME', CampusLaborContract.active.is_(True),
        CampusLaborContract.valid_from<=END, CampusLaborContract.valid_until>=START).with_for_update()))
    if any(c.valid_from!=START or c.valid_until!=END for c in current) or len(current)>1:
        raise ValueError('Vigencias solapadas; requiere revisión')
    if (current[0].id if current else None) != expected_id:
        raise ValueError('El contrato cambió; recarga antes de guardar')
    before = [snapshot(c) for c in current]
    for c in current: c.active=False
    db.flush()
    new = CampusLaborContract(employee_id=employee_id, campus_code='CME',valid_from=START,valid_until=END,
        import_id=receipt_id, active=True, **{k:data[k] for k in ('weekly_minutes','job_title','department_code','department_name','source_employee_key','source_sheet','source_row')})
    db.add(new); db.flush()
    return dict(employee_id=employee_id, before=before, after=snapshot(new))


def apply_preview(db, path, saved, staff_id):
    if not inspect(db.connection()).has_table('campus_labor_contracts'): raise ValueError('Falta migración 20261015_0016')
    staff = db.get(StaffUser, staff_id)
    if not staff or not staff.is_active or staff.email.lower()!='gaibarra@hotmail.com': raise ValueError('Autor no autorizado')
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(20261015)'))
        db.execute(text('LOCK TABLE employees, employee_departments, departments, labor_contracts, labor_contract_imports, campus_labor_contracts IN SHARE ROW EXCLUSIVE MODE'))
    request_hash = digest(['CME-2026-S2',saved['source_sha256']])
    previous=db.scalar(select(LaborContractImport).where(LaborContractImport.request_sha256==request_hash))
    if previous:
        if previous.reverted_at: raise ValueError('La importación fue revertida')
        return previous.id
    db.expire_all()
    fresh=preview(db,path)
    if digest(fresh)!=digest(saved): raise ValueError('La fuente o el catálogo cambió; genera otra vista previa')
    receipt=LaborContractImport(source_sha256=saved['source_sha256'],request_sha256=request_hash,
        source_name=saved['source_name'],staff_user_id=staff_id,audit={})
    db.add(receipt);db.flush()
    changes=[]
    for r in saved['rows']:
        if not r['eligible']:continue
        cs=campus_contract_map(db,[r['employee_id']])[r['employee_id']]
        c=covering_contract(cs,START,END,'CME')
        change=replace_contract(db,r['employee_id'],dict(r,source_sheet=r['sheet'],source_row=r['row']),receipt.id,c.id if c else None)
        changes.append(dict(change,key=r['key']))
    receipt.audit=dict(campus_code='CME',kind='campus_contract_import',valid_from=str(START),valid_until=str(END),
        changes=changes,source_rows=[{k:r[k] for k in ('key','employee_id','candidate_ids','source_employee_key','errors')} for r in saved['rows']])
    db.flush()
    return receipt.id


def export_preview(path, saved):
    book=Workbook();ws=book.active;ws.title='Revisión CME'
    ws.append(['Fila','Nombre Excel','Nombre aplicación','ID','Horas exactas','Puesto','Departamento laboral','Criterio','Estado'])
    for r in saved['rows']:
        ws.append([r['row'],r['source_name'],r['application_name'],r['employee_id'],r['weekly_minutes']/60 if r['weekly_minutes'] is not None else None,r['job_title'],r['department_name'],r['criterion'],'; '.join(r['errors']) if r['errors'] else 'Contrato pendiente' if r['weekly_minutes'] is None else 'Aprobable'])
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width=32
        for c in col:
            if isinstance(c.value,str):c.data_type='s'
    book.save(path)


def rollback(db, receipt_id, staff_id):
    from datetime import datetime, timezone
    staff=db.get(StaffUser,staff_id)
    if not staff or not staff.is_active or staff.email.lower()!='gaibarra@hotmail.com':raise ValueError('Autor no autorizado')
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(20261015)'))
        db.execute(text('LOCK TABLE campus_labor_contracts, labor_contract_imports IN SHARE ROW EXCLUSIVE MODE'))
    receipt=db.get(LaborContractImport,receipt_id)
    if not receipt or receipt.reverted_at or receipt.audit.get('campus_code')!='CME':raise ValueError('Operación no reversible')
    for change in receipt.audit['changes']:
        current=db.get(CampusLaborContract,change['after']['id'])
        if not current or snapshot(current)!=change['after']:raise ValueError('Existen cambios posteriores; no se sobrescriben')
        for old in change['before']:
            row=db.get(CampusLaborContract,old['id'])
            if not row or snapshot(row)!=(old|{'active':False}):raise ValueError('Una versión previa cambió')
    for change in receipt.audit['changes']:
        db.get(CampusLaborContract,change['after']['id']).active=False
    db.flush()
    for change in receipt.audit['changes']:
        for old in change['before']:db.get(CampusLaborContract,old['id']).active=True
    receipt.reverted_at=datetime.now(timezone.utc);receipt.reverted_by=staff_id
    db.flush()


def main():
    from app.db.session import SessionLocal, engine
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--apply',action='store_true');p.add_argument('--staff-id',type=int)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    saved_path=args.output/'preview.json'
    if args.apply:
        if not args.staff_id: p.error('--staff-id requerido')
        saved=json.loads(saved_path.read_text())
        from datetime import datetime, timezone
        backup=args.output/('before-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.dump')
        backup_database(engine,backup)
        with SessionLocal() as db:
            receipt_id=apply_preview(db,args.source,saved,args.staff_id);db.commit()
        result=dict(receipt_id=receipt_id,backup=str(backup),summary=saved['summary'])
        (args.output/'applied.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False))
    else:
        with SessionLocal() as db:
            if db.bind.dialect.name=='postgresql':db.execute(text('SET TRANSACTION READ ONLY'))
            saved=preview(db,args.source)
        with saved_path.open('x') as f:json.dump(saved,f,ensure_ascii=False,indent=2)
        export_preview(args.output/'revision.xlsx',saved)
        print(json.dumps(saved['summary'],ensure_ascii=False))


if __name__=='__main__':main()
