from datetime import time

import pytest
from app.services.semester_file_import import merge_blocks, normalized, parse_time, reconcile


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
