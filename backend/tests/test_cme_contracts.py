from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from copy import deepcopy
import pytest
from openpyxl import Workbook
from sqlalchemy import select
from fastapi.testclient import TestClient
from tests.test_labor_contracts import db  # noqa: F401
from app.models import StaffUser, Employee, CampusLaborContract, LaborContractImport, EmployeeDepartment
from app.services.cme_contract_import import preview, apply_preview, minutes, START, END, replace_contract
from app.services.labor_contracts import covering_contract, enrich_weekly
from app.main import app
from app.db.session import get_db
from app.dependencies.auth import get_current_actor, AuthenticatedActor


@pytest.fixture
def source(tmp_path):
    def make(hours=37.5, name='PEREZ GOMEZ ANA'):
        book=Workbook();ws=book.active;ws.title='Hoja1'
        ws.append(['CLAVE','NOMBRE COMPLETO','DEPARTAMENTO','NOMBRE DEL DEPTO','HORAS CONTRATO','NOMBRE DEL PUESTO'])
        ws.append([111,name,102,'Administración',hours,'Docente'])
        ws.append([222,'OTRA PERSONA',103,'Otro',40,'Otro'])
        path=tmp_path/'source.xlsx';book.save(path);return path
    return make


def owner(db):
    staff=db.get(StaffUser,10);staff.email='gaibarra@hotmail.com';db.commit();return staff


def test_preview_scope_and_exact_decimal(db,source):
    result=preview(db,source())
    assert result['summary']==dict(rows=2,eligible=1,pending=1,pending_hours=0)
    assert result['rows'][0]['weekly_minutes']==2250
    assert result['rows'][1]['errors']
    assert not list(db.scalars(select(CampusLaborContract)))


def test_migration_additive_and_reversible():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, inspect, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    file=Path(__file__).parents[1]/'alembic/versions/20261015_0016_campus_labor_contracts.py'
    spec=importlib.util.spec_from_file_location('migration',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE employees (id BIGINT PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE labor_contract_imports (id INTEGER PRIMARY KEY)'))
        module.op=Operations(MigrationContext.configure(conn))
        module.upgrade()
        assert inspect(conn).has_table('campus_labor_contracts')
        module.downgrade()
        assert not inspect(conn).has_table('campus_labor_contracts')
        assert inspect(conn).has_table('employees')


@pytest.mark.parametrize('value',[None,0,37.5,40])
def test_minutes(value):
    assert minutes(value)==(None if value is None else int(value*60))


@pytest.mark.parametrize('value',[-1,'NaN',169,Decimal('1.001')])
def test_bad_minutes(value):
    with pytest.raises(ValueError):minutes(value)


def test_import_audited_idempotent_and_does_not_change_profile(db,source):
    owner(db);path=source();saved=preview(db,path)
    before=(db.get(Employee,1).nombre,db.get(Employee,1).email)
    receipt=apply_preview(db,path,saved,10);db.commit()
    assert apply_preview(db,path,saved,10)==receipt
    assert len(list(db.scalars(select(CampusLaborContract))))==1
    contract=db.scalar(select(CampusLaborContract))
    assert contract.campus_code=='CME' and contract.weekly_minutes==2250
    assert contract.department_name=='Administración' and contract.job_title=='Docente'
    assert before==(db.get(Employee,1).nombre,db.get(Employee,1).email)
    assert db.get(LaborContractImport,receipt).audit['changes'][0]['after']['id']==contract.id


def test_pending_suppresses_legacy_only_in_cme_and_crossing_week(db,source):
    owner(db);path=source(None);saved=preview(db,path)
    apply_preview(db,path,saved,10);db.commit()
    current=db.scalar(select(CampusLaborContract))
    legacy=SimpleNamespace(active=True,valid_from=START,valid_until=END,weekly_minutes=2400)
    assert covering_contract([current,legacy],START,END,'Mérida') is current
    assert covering_contract([current,legacy],START,END,'Valladolid') is legacy
    assert current.weekly_minutes is None
    assert covering_contract([current,legacy],date(2026,7,27),date(2026,8,2),'Mérida') is None
    rows=[dict(employee_id=1,contracted_seconds=28800,difference_seconds=-28800)]
    assert enrich_weekly(db,rows,START,END,campus='Mérida')[0]['labor_contract_seconds'] is None


def test_concurrent_changes_abort_import(db,source):
    owner(db);path=source();saved=preview(db,path)
    db.get(Employee,1).nombre='Cambio posterior';db.commit()
    with pytest.raises(ValueError,match='cambió'):apply_preview(db,path,saved,10)
    db.rollback();assert not list(db.scalars(select(CampusLaborContract)))


def test_reversal_preserves_data_and_rejects_later_changes(db,source):
    from app.services.cme_contract_import import rollback
    owner(db);path=source();saved=preview(db,path)
    receipt=apply_preview(db,path,saved,10);db.commit()
    current=db.scalar(select(CampusLaborContract))
    current.job_title='Edición posterior';db.commit()
    with pytest.raises(ValueError,match='posteriores'):rollback(db,receipt,10)
    db.rollback();current.job_title='Docente';db.commit()
    rollback(db,receipt,10);db.commit()
    assert not current.active
    assert db.get(LaborContractImport,receipt).reverted_at is not None


def test_duplicate_identity_not_applied(db,source):
    db.add(Employee(id=99,nombre='PEREZ GOMEZ ANA',email='duplicate@test.test',departamento='CME'))
    db.commit()
    assert not preview(db,source())['rows'][0]['eligible']


def test_typo_unique_and_source_key_is_not_internal_id(db,source):
    row=preview(db,source(name='PEREZ GOMEZ ANNA'))['rows'][0]
    assert row['eligible'] and row['employee_id']==1
    assert row['source_employee_key']=='111'


def test_manual_api_access_conflicts_and_pending(db,source):
    staff=owner(db);previous=app.dependency_overrides.copy()
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_actor]=lambda:AuthenticatedActor(actor_type='staff',is_admin=True,must_change_password=False,staff=staff)
    try:
        with TestClient(app) as client:
            payload=dict(expected_id=None,weekly_hours='37.5',job_title='Docente',department_name='Laboral',department_code='102')
            assert client.get('/employees/manage/1/contract').status_code==200
            result=client.put('/employees/manage/1/contract',json=payload)
            assert result.status_code==200,result.text
            assert result.json()['current']['weekly_minutes']==2250
            assert client.put('/employees/manage/1/contract',json=payload).status_code==409
            payload.update(expected_id=result.json()['current']['id'],weekly_hours=None)
            pending=client.put('/employees/manage/1/contract',json=payload)
            assert pending.json()['current']['weekly_minutes'] is None
            assert len(pending.json()['history'])==2
            assert client.put('/employees/manage/2/contract',json=payload).status_code==403
            assert client.put('/employees/manage/1/contract',json=payload|{'weekly_hours':'1.001'}).status_code==422
            staff.email='other@example.com'
            assert client.get('/employees/manage/1/contract').status_code==403
            assert client.put('/employees/manage/1/contract',json=payload).status_code==403
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)
