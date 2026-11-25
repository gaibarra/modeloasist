from types import SimpleNamespace
from collections import defaultdict
from openpyxl import Workbook
from app.services.revised_schedule_import import intervals, read_source, resolve


def test_duplicates_adjacent_and_breaks():
    result,overlaps,duplicates=intervals({0:[(420,480),(420,480),(480,540),(600,660)]})
    assert duplicates==1 and overlaps==[]
    assert [(r['start'],r['end']) for r in result]==[('07:00','09:00'),('10:00','11:00')]


def test_nonidentical_overlap_is_flagged():
    result,overlaps,_=intervals({2:[(420,600),(480,660)]})
    assert overlaps==[2]
    assert result==[dict(weekday=2,start='07:00',end='11:00')]


def test_alias_conflicting_with_exact_blocks():
    es=[SimpleNamespace(id=1,nombre='PEREZ LOPEZ ANA'),SimpleNamespace(id=2,nombre='PEREZ LOPEZ ANNA')]
    assert resolve('PÉREZ LOPEZ ANA',es,{'PEREZLOPEZANA':{2}})[0] is None
    assert resolve('PÉREZ LOPEZ ANA',es,{})[0]==1


def test_word_difference_requires_audited_alias():
    es=[SimpleNamespace(id=1,nombre='ACEVEDO CONTRERAS PAULO CESAR')]
    assert resolve('ACEVEDO CONTRERAS PAULO',es,{})[0] is None
    assert resolve('ACEVEDO CONTRERAS PAULO',es,{'ACEVEDOCONTRERASPAULO':{1}})[0]==1


def test_small_difference_requires_surnames_and_unique_candidate():
    es=[SimpleNamespace(id=1,nombre='PEREZ LOPEZ ANA')]
    assert resolve('PEREZ LOPEZ ANNA',es,{})[0]==1
    assert resolve('PEREZ LOPES ANA',es,{})[0] is None
    assert resolve('PEREZ LOPEZ ANNA',es+[SimpleNamespace(id=2,nombre='PEREZ LOPEZ ANAH')],{})[0] is None


def test_single_sheet_names_and_invalid_rows(tmp_path):
    w=Workbook();s=w.active
    s.append(['empleadoId','EmpleadoNombre','escClave','progClave','matClave','matNombre','gpoClave','diaLetra','Inicio','Fin'])
    s.append([1,'PEÑA LEON JORGE','','','','','','Lunes','07:00 hrs','10:00 hrs'])
    s.append([1,'PEÑA LEON JORGE IGNACIO','','','','','','Martes','10:00','09:00'])
    p=tmp_path/'source.xlsx';w.save(p)
    people=read_source(p)
    assert len(people)==1 and len(people[0]['names'])==2
    assert len(people[0]['errors'])==1 and len(people[0]['rows'])==2


def test_apply_concurrency_idempotency_and_guarded_rollback(tmp_path):
    import copy
    import pytest
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.db.base import Base
    from app.models import Employee, StaffSemesterSchedule
    from app.services.revised_schedule_import import preview, apply_review, rollback_review
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    w=Workbook();s=w.active
    s.append(['empleadoId','EmpleadoNombre','escClave','progClave','matClave','matNombre','gpoClave','diaLetra','Inicio','Fin'])
    for eid,name in [(1,'PEREZ LOPEZ ANA'),(2,'LOPEZ PEREZ LUIS')]:
        s.append([eid,name,'','','','','','Lunes','07:00','15:00'])
    source=tmp_path/'source.xlsx';w.save(source)
    with Session(engine) as db:
        for eid,name in [(1,'PEREZ LOPEZ ANA'),(2,'LOPEZ PEREZ LUIS')]:
            db.add(Employee(id=eid,nombre=name,email=f'{eid}@test.local',departamento='CME-Salud',campus='Mérida'))
        db.commit()
        review=preview(db,source)
        with pytest.raises(ValueError,match='no aprobables'):
            apply_review(db,source,review,{999},'test','backup')
        changed=copy.deepcopy(review);changed['state']='stale'
        with pytest.raises(ValueError,match='Cambió'):
            apply_review(db,source,changed,{1},'test','backup')
        rid=apply_review(db,source,review,{1,2},'test','backup');db.commit()
        assert apply_review(db,source,review,{1,2},'test','backup')==rid
        assert len(list(db.scalars(select(StaffSemesterSchedule))))==2
        p=db.scalar(select(StaffSemesterSchedule).where(StaffSemesterSchedule.employee_id==1))
        from datetime import datetime
        p.updated_at=datetime(2030,1,1);db.commit()
        result=rollback_review(db,rid,'test rollback','backup');db.commit()
        assert result['skipped']==[1] and result['restored']==[2]
        assert len(list(db.scalars(select(StaffSemesterSchedule))))==1


def test_preview_blocks_whole_week_excludes_bajas_and_preserves_absent(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.base import Base
    from app.models import Employee
    from app.services.revised_schedule_import import preview
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    w=Workbook();s=w.active
    s.append(['empleadoId','EmpleadoNombre','escClave','progClave','matClave','matNombre','gpoClave','diaLetra','Inicio','Fin'])
    s.append([11,'PEREZ LOPEZ ANA','','','','','','Lunes','07:00','10:00'])
    s.append([12,'PEREZ LOPEZ ANA','','','','','','Lunes','09:00','11:00'])
    s.append([13,'LOPEZ PEREZ LUIS','','','','','','Lunes','07:00','15:00'])
    source=tmp_path/'source.xlsx';w.save(source)
    with Session(engine) as db:
        db.add_all([Employee(id=1,nombre='PEREZ LOPEZ ANA',email='1@test.local',departamento='CME-Salud'),Employee(id=2,nombre='LOPEZ PEREZ LUIS',email='2@test.local',departamento='BAJAS NOMINA'),Employee(id=3,nombre='AUSENTE DEL ARCHIVO',email='3@test.local',departamento='CME-Salud')]);db.commit()
        r=preview(db,source)
        assert len(r['updates'])==1 and r['updates'][0]['status']=='Pendiente por inconsistencia'
        assert r['issues'][0]['status']=='Baja excluida'
        assert [p['employee_id'] for p in r['absent']]==[3]
        assert not db.new and not db.dirty
