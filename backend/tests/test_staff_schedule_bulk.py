from datetime import date, time

import pytest

from app.services.staff_schedule_bulk import BulkInstructionError, parse_bulk_instruction
from app.services.official_holidays import official_holiday_name


def test_parser_handles_entry_with_spanish_range_and_ampm():
    result = parse_bulk_instruction("Del 17 al 23 de agosto la entrada para todos será a las 9 am", today=date(2026, 8, 1))
    assert result.operation == "entry"
    assert result.start_date == date(2026, 8, 17)
    assert result.end_date == date(2026, 8, 23)
    assert result.start == time(9)


def test_parser_handles_full_schedule_24_hour_time():
    result = parse_bulk_instruction("Del 17 al 23 de agosto horario para todos de 09:30 a 15:00", today=date(2026, 8, 1))
    assert result.operation == "replace"
    assert result.start == time(9, 30)
    assert result.end == time(15)


@pytest.mark.parametrize("instruction", [
    "Del 17 al 23 de agosto para todos",
    "Del 23 al 17 de agosto la entrada para todos será a las 9 am",
    "Del 17 al 23 de agosto la entrada para todos será a las 9 am y 10 am",
])
def test_parser_rejects_ambiguous_or_incomplete_instruction(instruction: str):
    with pytest.raises(BulkInstructionError):
        parse_bulk_instruction(instruction, today=date(2026, 8, 1))


def test_mexican_official_holidays_include_2026_mandatory_dates():
    assert official_holiday_name(date(2026, 2, 2)) == "Conmemoración de la Constitución"
    assert official_holiday_name(date(2026, 3, 16)) == "Conmemoración del natalicio de Benito Juárez"
    assert official_holiday_name(date(2026, 9, 16)) == "Independencia de México"
    assert official_holiday_name(date(2026, 4, 2)) is None
