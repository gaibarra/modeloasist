from datetime import date, time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from app.core.config import Settings
from app.models.employee import Employee
from app.services.attendance_import import AttendanceImportService, ParsedAttendanceRow


def resolve(employees, name, identifier=3174, department="CCH-Derecho"):
    db = MagicMock()
    db.query.return_value.all.return_value = employees
    service = AttendanceImportService(db=db, settings=Settings())
    row = ParsedAttendanceRow(2, identifier, name, department, date(2026, 9, 14), time(7), None, None, None)
    service._assign_missing_employee_ids([row])
    return row


def employee(identifier, name, external=None, department="CCH-Derecho"):
    return Employee(id=identifier, nombre=name, external_employee_id=external, departamento=department)


def test_external_biometric_id_wins_over_local_id_collision():
    original = employee(6857890589, "CAAMAL DE LANDA ELDA PAULINA", 3174)
    duplicate = employee(3174, "CAAMAL DE LANDA ELDA PAULINA CAAMAL DE LANDA")
    row = resolve([original, duplicate], duplicate.nombre)
    assert row.employee_id == original.id
    assert row.nombre == duplicate.nombre  # preserve raw source evidence


def test_repeated_compound_surname_without_external_id():
    original = employee(40, "CAAMAL DE LANDA ELDA PAULINA")
    assert resolve([original], "CAAMAL DE LANDA ELDA PAULINA CAAMAL DE LANDA").employee_id == 40


def test_repeated_surname_normalizes_accents_and_spacing():
    original = employee(40, "PEÑA CARDENETA NAHIM ENRIQUE")
    assert resolve([original], "PENA  CARDENETA NAHIM ENRIQUE PENA CARDENETA").employee_id == 40


def test_no_cross_department_repeated_name_guess():
    original = employee(40, "PEÑA CARDENETA NAHIM ENRIQUE", department="CVA-Derecho")
    row = resolve([original], "PEÑA CARDENETA NAHIM ENRIQUE PEÑA CARDENETA")
    assert row.employee_id == 3174 and row.lookup_reason == "name_search_no_match"


def test_ambiguous_repeated_names_block_creation():
    people = [employee(i, "CAAMAL DE LANDA ELDA PAULINA") for i in (40, 41)]
    with pytest.raises(HTTPException) as exc:
        resolve(people, "CAAMAL DE LANDA ELDA PAULINA CAAMAL DE LANDA")
    assert exc.value.status_code == 422


def test_ambiguous_external_id_blocks_creation():
    with pytest.raises(HTTPException):
        resolve([employee(i, "PERSONA", 3174) for i in (40, 41)], "PERSONA")
