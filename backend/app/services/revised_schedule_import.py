"""Reviewed single-sheet schedules: preview first, explicit approval, immutable receipts."""
import argparse
from copy import deepcopy
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
import hashlib
import json
import os
from pathlib import Path
from difflib import get_close_matches

import openpyxl
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select, text
from app.db.session import SessionLocal, engine
from app.models import Employee, EmployeeDepartment, Department, StaffSemesterSchedule, StaffSemesterScheduleInterval, StaffScheduleFileImport, CampusLaborContract, LaborContract
from app.services.semester_file_import import compact_name, normalized, parse_time, merge_blocks, hhmm, DAYS
from app.services.cme_contract_import import distance
from app.services.labor_contract_import import digest, backup_database
from app.services.report_eligibility import departure_snapshot


def intervals(blocks):
    result, overlaps, duplicates = [], [], 0
    for day, pairs in sorted(blocks.items()):
        duplicates += len(pairs) - len(set(pairs))
        end = -1
        for a, b in sorted(set(pairs)):
            if a < end:
                overlaps.append(day)
            end = max(end, b)
        result.extend(dict(weekday=day, start=hhmm(a), end=hhmm(b)) for a, b in merge_blocks(pairs))
    return result, sorted(set(overlaps)), duplicates


def read_source(path):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    groups = {}
    for sheet in book:
        if sheet.max_row == 1 and sheet.cell(1, 1).value is None:
            continue
        header = [normalized(v) for v in next(sheet.iter_rows(values_only=True))]
        expected = ['empleadoId', 'EmpleadoNombre', 'escClave', 'progClave', 'matClave', 'matNombre', 'gpoClave', 'diaLetra', 'Inicio', 'Fin']
        if header != [normalized(v) for v in expected]:
            raise ValueError('Encabezados inesperados: ' + sheet.title)
        for number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
            if not any(v is not None for v in row):
                continue
            key = str(row[0]) if row[0] is not None else f'missing:{sheet.title}:{number}'
            p = groups.setdefault(key, dict(source_id=key, names=[], rows=[], blocks=defaultdict(list), errors=[]))
            if row[1] not in p['names']:
                p['names'].append(row[1])
            p['rows'].append(dict(sheet=sheet.title, row=number, values=list(row)))
            try:
                if row[0] is None or not row[1]:
                    raise ValueError('Falta nombre o identificador de origen')
                day = [normalized(d) for d in DAYS].index(normalized(row[7]))
                a, b = parse_time(row[8]), parse_time(row[9])
                if a >= b:
                    raise ValueError('Intervalo inválido o nocturno: requiere revisión')
                p['blocks'][day].append((a, b))
            except ValueError as exc:
                p['errors'].append(f'{sheet.title}:{number}: {exc}')
    book.close()
    for p in groups.values():
        p['intervals'], p['overlaps'], p['duplicates'] = intervals(p.pop('blocks'))
    return list(groups.values())


def resolve(name, employees, aliases):
    key = compact_name(name or '')
    exact = {e.id for e in employees if compact_name(e.nombre) == key}
    known = aliases.get(key, set()) & {e.id for e in employees}
    if len(exact | known) == 1:
        return next(iter(exact | known)), 'Nombre normalizado' if exact else 'Equivalencia auditada'
    if exact or known:
        return None, 'Identidad ambigua o equivalencias contradictorias'
    tokens = normalized(name or '').split()
    # Conservative: surname prefixes must be unchanged; compound surnames do not
    # gain extra latitude. Word omissions require a previously audited alias.
    near = {e.id for e in employees if len(tokens) >= 3 and normalized(e.nombre).split()[:2] == tokens[:2]
            and len(normalized(e.nombre).split()) == len(tokens) and distance(key, compact_name(e.nombre)) <= 2}
    return (next(iter(near)), 'Hasta dos caracteres, apellidos iguales') if len(near) == 1 else (None, 'Identidad pendiente')


def profile_snapshot(p):
    if p is None:
        return None
    return dict(id=p.id, updated_at=str(p.updated_at), author=p.updated_by_staff_user_id,
                intervals=[dict(weekday=i.weekday, start=i.start.strftime('%H:%M'), end=i.end.strftime('%H:%M')) for i in p.intervals])


def minutes(items):
    return sum(parse_time(i['end']) - parse_time(i['start']) for i in items)


def preview(db, source):
    people = read_source(source)
    employees = list(db.scalars(select(Employee).order_by(Employee.id)))
    by_id = {e.id: e for e in employees}
    aliases = defaultdict(set)
    receipts = list(db.scalars(select(StaffScheduleFileImport).order_by(StaffScheduleFileImport.id)))
    for receipt in receipts:
        audit = receipt.audit or {}
        if audit.get('kind') == 'schedule_review_rollback':
            continue
        for u in audit.get('updates', []):
            for s in u.get('sources', []):
                for name in [s.get('name'), s.get('original_name'), *s.get('names', [])]:
                    if name:
                        aliases[compact_name(name)].add(u['employee_id'])
    excluded, _ = departure_snapshot(db)
    links = defaultdict(list)
    for eid, d in db.execute(select(EmployeeDepartment.employee_id, Department).join(Department)):
        links[eid].append(dict(id=d.id, name=d.name, campus=d.campus))
    profiles = {p.employee_id: p for p in db.scalars(select(StaffSemesterSchedule).where(StaffSemesterSchedule.academic_year == 2026, StaffSemesterSchedule.semester == 2))}
    contracts = defaultdict(list)
    for c in db.scalars(select(CampusLaborContract).where(CampusLaborContract.active.is_(True))):
        if str(c.valid_from) <= '2026-08-01' and str(c.valid_until) >= '2026-12-31':
            contracts[c.employee_id].append(dict(campus=c.campus_code, minutes=c.weekly_minutes))
    for c in db.scalars(select(LaborContract).where(LaborContract.active.is_(True))):
        if not contracts[c.employee_id] and str(c.valid_from) <= '2026-08-01' and str(c.valid_until) >= '2026-12-31':
            contracts[c.employee_id].append(dict(campus='General', minutes=c.weekly_minutes))
    grouped, issues = defaultdict(list), []
    for p in people:
        resolutions = [resolve(n, employees, aliases) for n in p['names']]
        ids = {i for i, _ in resolutions if i is not None}
        p['method'] = '; '.join(sorted({m for _, m in resolutions}))
        p['candidate_ids'] = sorted(ids)
        if len(ids) != 1 or any(i is None for i, _ in resolutions):
            p['status'] = 'Pendiente de identidad'
            if len(p['names']) > 1:
                p['errors'].append('Variantes de nombre sin equivalencia única')
            suggestions = get_close_matches(normalized(p['names'][0] or ''), [normalized(e.nombre) for e in employees], n=3, cutoff=.78)
            p['suggestions'] = [dict(id=e.id, name=e.nombre) for e in employees if normalized(e.nombre) in suggestions]
            issues.append(p)
            continue
        eid = next(iter(ids))
        p['employee_id'] = eid
        if eid in excluded:
            p['status'] = 'Baja excluida'; issues.append(p)
        else:
            grouped[eid].append(p)
    updates = []
    for eid, sources in grouped.items():
        e = by_id[eid]
        blocks = defaultdict(list)
        for p in sources:
            for i in p['intervals']:
                blocks[i['weekday']].append((parse_time(i['start']), parse_time(i['end'])))
        proposed, overlap, _ = intervals(blocks)
        errors = [v for p in sources for v in p['errors']]
        overlap = sorted(set(overlap + [d for p in sources for d in p['overlaps']]))
        # Any unresolved source that could belong to this person prevents partial import.
        if any(eid in p['candidate_ids'] or any(compact_name(n or '') == compact_name(e.nombre) for n in p['names']) for p in issues):
            errors.append('Otra fuente de esta persona está pendiente')
        old = profile_snapshot(profiles.get(eid))
        action = 'Completar' if old is None else 'Sin cambios' if old['intervals'] == proposed else 'Actualizar'
        status = 'Pendiente por inconsistencia' if errors or overlap else 'Propuesto para confirmación'
        updates.append(dict(employee_id=eid, name=e.nombre, email=e.email, campus=e.campus,
            departments=links[eid], sources=sources, previous=old, intervals=proposed,
            weekly_minutes=minutes(proposed), contracts=contracts[eid], overlaps=overlap, errors=errors, action=action, status=status))
    touched = set(grouped) | {eid for p in issues for eid in p['candidate_ids']}
    absent = [dict(employee_id=e.id, name=e.nombre, campus=e.campus, departments=links[e.id], status='Sin información en esta revisión') for e in employees if e.id not in touched and e.id not in excluded]
    state = digest(dict(employees=[(e.id,e.nombre,e.email,e.departamento,e.campus) for e in employees], links=dict(links), excluded=excluded,
                        profiles={eid:profile_snapshot(p) for eid,p in profiles.items()}, contracts=dict(contracts), receipts=[r.id for r in receipts]))
    return dict(version=1,source_name=source.name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),state=state,
        year=2026,semester=2,updates=sorted(updates,key=lambda u:normalized(u['name'])),issues=issues,absent=absent,
        summary=dict(source_people=len(people),source_rows=sum(len(p['rows']) for p in people),duplicates=sum(p['duplicates'] for p in people),
                     ready=dict(Counter(u['action'] for u in updates if u['status']=='Propuesto para confirmación')),
                     blocked_people=sum(u['status']!='Propuesto para confirmación' for u in updates),issues=dict(Counter(p['status'] for p in issues)),absent=len(absent)))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)); path.chmod(0o600)


def export(review, path):
    w=openpyxl.Workbook();s=w.active;s.title='Resumen'
    s.append(['Estado','VISTA PREVIA: NO APLICADA']);s.append(['Vigencia','01 agosto–31 diciembre 2026'])
    for k,v in review['summary'].items():s.append([k,json.dumps(v,ensure_ascii=False) if isinstance(v,dict) else v])
    def fmt(items):return ' | '.join(f"{DAYS[i['weekday']]} {i['start']}–{i['end']}" for i in items)
    for title,items in [('Propuestas',[u for u in review['updates'] if u['status']=='Propuesto para confirmación']),('Inconsistencias',[u for u in review['updates'] if u['status']!='Propuesto para confirmación'])]:
        s=w.create_sheet(title);s.append(['ID','Nombre aplicación','Nombres archivo','Campus','Departamentos','Resultado','Método','Anterior','Propuesto','Horas anteriores','Horas propuestas','Contratos por campus','Diferencia horario-contrato','Advertencias'])
        for u in items:
            cs=u['contracts'];cm=cs[0]['minutes'] if len(cs)==1 else None
            notes=u['errors']+[('Solapamiento: '+', '.join(DAYS[d] for d in u['overlaps']))] if u['overlaps'] else list(u['errors'])
            if len(cs)>1:notes.append('Múltiples campus: horario sin atribución por campus; no sumar contratos')
            if cm is None:notes.append('Sin referencia contractual única completa')
            s.append([u['employee_id'],u['name'],' / '.join(n or '' for p in u['sources'] for n in p['names']),u['campus'],', '.join(d['name'] for d in u['departments']),u['action'],' / '.join(p['method'] for p in u['sources']),fmt((u['previous'] or {}).get('intervals',[])),fmt(u['intervals']),minutes(u['previous']['intervals'])/60 if u['previous'] else None,u['weekly_minutes']/60,'; '.join(f"{c['campus']}: {c['minutes']/60 if c['minutes'] is not None else 'Pendiente'}" for c in cs),(u['weekly_minutes']-cm)/60 if cm is not None else None,'; '.join(notes)])
    s=w.create_sheet('Fuentes originales');s.append(['ID origen','Nombre','Hoja','Fila','Día','Inicio','Fin','Escuela','Programa','Materia','Grupo'])
    sources=[p for u in review['updates'] for p in u['sources']]+review['issues']
    for p in sources:
        for r in p['rows']:
            v=r['values'];s.append([p['source_id'],v[1],r['sheet'],r['row'],v[7],str(v[8]),str(v[9]),v[2],v[3],v[5],v[6]])
    s=w.create_sheet('Identidades y bajas');s.append(['ID origen','Nombres','Estado','Candidatos','Advertencias'])
    for p in review['issues']:s.append([p['source_id'],' / '.join(n or '' for n in p['names']),p['status'],json.dumps(p.get('suggestions',p['candidate_ids']),ensure_ascii=False),'; '.join(p['errors']+(['Solapamiento: '+', '.join(DAYS[d] for d in p['overlaps'])] if p['overlaps'] else []))])
    s=w.create_sheet('Sin información');s.append(['ID','Nombre','Campus','Departamentos','Estado','Solicitud'])
    for p in review['absent']:s.append([p['employee_id'],p['name'],p['campus'],', '.join(d['name'] for d in p['departments']),p['status'],'Confirmar bloques de entrada y salida por día para agosto–diciembre 2026.'])
    for s in w:
        s.freeze_panes='A2';s.auto_filter.ref=s.dimensions
        for cell in s[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='17365D')
        for col in s.columns:
            s.column_dimensions[col[0].column_letter].width=min(65,max(16,max(len(str(c.value or '')) for c in col)+2))
            for cell in col:
                if cell.data_type=='f':cell.data_type='s'
    w.save(path);path.chmod(0o600)


def lock_review(db):
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text("SET LOCAL lock_timeout='15s'"))
        db.execute(text('SELECT pg_advisory_xact_lock(20260914)'))
        db.execute(text('LOCK TABLE employees, employee_departments, departments, staff_semester_schedules, staff_semester_schedule_intervals, staff_schedule_file_imports, campus_labor_contracts, labor_contracts IN SHARE ROW EXCLUSIVE MODE'))


def rollback_review(db, receipt_id, authorization, backup):
    if not authorization.strip():
        raise ValueError('Reversión requiere autorización')
    lock_review(db)
    receipt = db.get(StaffScheduleFileImport, receipt_id)
    if receipt is None or receipt.audit.get('kind') != 'reviewed_schedule_import':
        raise ValueError('Operación no compatible con esta reversión')
    request = digest(['rollback-reviewed-schedules', receipt_id])
    if db.scalar(select(StaffScheduleFileImport).where(StaffScheduleFileImport.source_sha256 == request)):
        raise ValueError('Operación ya revertida')
    restored, skipped = [], []
    for u in receipt.audit['updates']:
        if u['action'] == 'Sin cambios':
            continue
        p = db.scalar(select(StaffSemesterSchedule).where(StaffSemesterSchedule.employee_id == u['employee_id'], StaffSemesterSchedule.academic_year == 2026, StaffSemesterSchedule.semester == 2))
        if profile_snapshot(p) != u['after']:
            skipped.append(u['employee_id']); continue
        if u['previous'] is None:
            db.delete(p)
        else:
            old = u['previous']
            p.intervals = [StaffSemesterScheduleInterval(weekday=i['weekday'], start=time.fromisoformat(i['start']), end=time.fromisoformat(i['end'])) for i in old['intervals']]
            p.updated_by_staff_user_id = old['author']
            p.updated_at = datetime.now(timezone.utc)
        restored.append(u['employee_id'])
    reversal = StaffScheduleFileImport(source_sha256=request, source_name=receipt.source_name, academic_year=2026, semester=2,
        audit=dict(kind='schedule_review_rollback', original_receipt=receipt_id, restored=restored, skipped=skipped, authorization=authorization, backup=str(backup)))
    db.add(reversal); db.flush()
    return dict(receipt_id=reversal.id, restored=restored, skipped=skipped)


def apply_review(db, source, review, approved, authorization, backup):
    if not approved or not authorization.strip():raise ValueError('Se requiere selección y autorización explícita')
    request=digest([review['source_sha256'],sorted(approved),digest(review)])
    lock_review(db)
    existing=db.scalar(select(StaffScheduleFileImport).where(StaffScheduleFileImport.source_sha256==request,StaffScheduleFileImport.academic_year==2026,StaffScheduleFileImport.semester==2))
    if existing:
        reverted = db.scalar(select(StaffScheduleFileImport).where(StaffScheduleFileImport.source_sha256 == digest(['rollback-reviewed-schedules', existing.id])))
        if reverted:raise ValueError('Operación revertida: generar una revisión nueva')
        return existing.id
    fresh=preview(db,source)
    if digest(fresh)!=digest(review):raise ValueError('Cambió el archivo o la base desde la revisión: regenerar vista previa')
    eligible={u['employee_id']:u for u in review['updates'] if u['status']=='Propuesto para confirmación'}
    if not set(approved)<=set(eligible):raise ValueError('Selección contiene personas no aprobables')
    selected=[deepcopy(eligible[i]) for i in sorted(approved)]
    for u in selected:
        if u['action']=='Sin cambios':continue
        p=db.scalar(select(StaffSemesterSchedule).where(StaffSemesterSchedule.employee_id==u['employee_id'],StaffSemesterSchedule.academic_year==2026,StaffSemesterSchedule.semester==2))
        if p is None:
            p=StaffSemesterSchedule(employee_id=u['employee_id'],academic_year=2026,semester=2);db.add(p)
        p.intervals=[StaffSemesterScheduleInterval(weekday=i['weekday'],start=time.fromisoformat(i['start']),end=time.fromisoformat(i['end'])) for i in u['intervals']]
        p.updated_at=datetime.now(timezone.utc);p.updated_by_staff_user_id=None
        db.flush()
        db.refresh(p)
        u['after']=profile_snapshot(p)
        if u['after']['intervals']!=u['intervals']:raise ValueError('Verificación de persistencia fallida')
    receipt=StaffScheduleFileImport(source_sha256=request,source_name=source.name,academic_year=2026,semester=2,
        audit=dict(kind='reviewed_schedule_import',file_sha256=review['source_sha256'],review_sha256=digest(fresh),authorization=authorization,backup=str(backup),updates=selected))
    db.add(receipt);db.flush();return receipt.id


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--rollback',type=int)
    parser.add_argument('--apply-review',type=Path);parser.add_argument('--approved-ids',type=Path);parser.add_argument('--authorization')
    args=parser.parse_args();os.umask(0o077);args.output.mkdir(parents=True,exist_ok=True);args.output.chmod(0o700)
    if args.rollback:
        if not args.authorization:parser.error('Falta autorización de reversión')
        backup=args.output/('antes-reversion-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.dump')
        backup_database(engine,backup)
        with SessionLocal.begin() as db:result=rollback_review(db,args.rollback,args.authorization,backup)
        save(args.output/'reversion.json',result);print(json.dumps(result))
    elif args.apply_review:
        if not args.approved_ids or not args.authorization:parser.error('Faltan IDs aprobados o autorización')
        review=json.loads(args.apply_review.read_text());approved=json.loads(args.approved_ids.read_text())
        backup=args.output/('antes-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.dump')
        backup_database(engine,backup)
        with SessionLocal.begin() as db:rid=apply_review(db,args.source,review,set(approved),args.authorization,backup)
        save(args.output/'aplicado.json',dict(receipt_id=rid));print(json.dumps(dict(receipt_id=rid)))
    else:
        with SessionLocal() as db:
            if engine.dialect.name=='postgresql':db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
            review=preview(db,args.source)
        save(args.output/'revision.json',review);export(review,args.output/'Revision_horarios.xlsx');print(json.dumps(review['summary'],ensure_ascii=False))

if __name__=='__main__':main()
