from datetime import time

import pytest
from app.services.semester_file_import import merge_blocks, normalized, parse_time, reconcile


def test_workbook_auxiliary_rows_and_spacing_variants(tmp_path):
    from openpyxl import Workbook
    from app.services.semester_file_import import read_workbook
    book = Workbook()
    book.remove(book.active)
    headers = ['empleadoId', 'empleadoNombre', 'escClave', 'progClave', 'matClave',
               'matNombre', 'gpoClave', 'diaLetra', 'Inicio', 'Fin']
    for title in ('CME', 'CVA', 'CCH'):
        ws = book.create_sheet(title)
        ws.append(headers)
    ws = book['CME']
    ws.append([1, 'HERNANDEZDOMINGUEZANDRES JESUS', '', '', '', '', '', 'Lunes', '07:00', '08:00'])
    ws.append([1, 'HERNÁNDEZ DOMINGUEZ ANDRES JESUS', '', '', '', '', '', 'Lunes', '08:00', '09:00'])
    ws.append([None] * 10 + [4, 12])
    ws.append([2, 'OTRA PERSONA', '', '', '', '', '', 'Martes', '07:00', '08:00'])
    ws.append([2, 'PERSONA DISTINTA', '', '', '', '', '', 'Martes', '08:00', '09:00'])
    path = tmp_path / 'workbook.xlsx'
    book.save(path)
    people = read_workbook(path)
    assert len(people) == 2
    assert not people[0]['errors']
    assert people[0]['intervals'] == [{'weekday': 0, 'start': '07:00', 'end': '09:00'}]
    assert people[1]['errors']  # Different names sharing an ID still block import.


def test_merge_only_overlapping_or_touching_intervals():
    assert merge_blocks([(420, 480), (420, 480), (450, 540), (540, 600), (660, 720)]) == [[420, 600], [660, 720]]


@pytest.mark.parametrize("value", ["25:00 hrs", "10:70", None, "9 AM"])
def test_invalid_time_is_rejected(value):
    with pytest.raises(ValueError):
        parse_time(value)


def test_time_and_accent_normalization():
    assert parse_time("07:30 hrs") == parse_time(time(7, 30)) == 450
    assert normalized("  PÉREZ   GÓMEZ ") == "PEREZ GOMEZ"


def person(**overrides):
    return {"sheet": "CME", "campus": "Mérida", "source_id": "999", "name": "PÉREZ GÓMEZ ANA", "rows": [2], "errors": [], "intervals": [{"weekday": 0, "start": "07:00", "end": "15:00"}], **overrides}


def test_external_id_cannot_assign_another_person():
    employees = [{"id": 999, "name": "OTRA PERSONA", "campuses": ["Mérida"]}, {"id": 12, "name": "PEREZ GOMEZ ANA", "campuses": ["Mérida"]}]
    updates, issues = reconcile([person()], employees)
    assert [u["employee_id"] for u in updates] == [12]
    assert not issues


def test_wrong_campus_and_ambiguous_names_are_not_imported():
    employees = [{"id": 1, "name": "PEREZ GOMEZ ANA", "campuses": ["Chetumal"]}]
    assert not reconcile([person()], employees)[0]
    employees = [{"id": i, "name": "PEREZ GOMEZ ANA", "campuses": ["Mérida"]} for i in (1, 2)]
    assert not reconcile([person()], employees)[0]


def test_invalid_source_prevents_partial_confirmation():
    employees = [{"id": 1, "name": "PEREZ GOMEZ ANA", "campuses": ["Mérida"]}]
    updates, issues = reconcile([person(), person(source_id="1000", errors=["Hora inválida"])], employees)
    assert not updates
    assert len(issues) == 2
