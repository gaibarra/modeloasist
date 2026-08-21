"""Controlled parsing for staff bulk schedule instructions.

This intentionally accepts a small, documented Spanish grammar.  It does not
use an LLM, so a sentence is either fully understood or rejected before any
schedule can be changed.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, time


MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_RANGE = re.compile(r"\bdel\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?\b")
_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?\s*m\.?|p\.?\s*m\.?)?\b")


class BulkInstructionError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedBulkInstruction:
    instruction: str
    operation: str
    start_date: date
    end_date: date
    start: time | None = None
    end: time | None = None


def parse_bulk_instruction(instruction: str, *, today: date | None = None) -> ParsedBulkInstruction:
    raw = instruction.strip()
    if not raw:
        raise BulkInstructionError("Escribe una instrucción para interpretar.")
    normalized = _normalize(raw)
    date_match = _RANGE.search(normalized)
    if not date_match:
        raise BulkInstructionError("Indica un rango como “del 17 al 23 de agosto”.")
    start_day, end_day, month_name, raw_year = date_match.groups()
    month = MONTHS.get(month_name)
    if month is None:
        raise BulkInstructionError("El mes indicado no es válido.")
    year = int(raw_year) if raw_year else (today or date.today()).year
    try:
        start_date = date(year, month, int(start_day))
        end_date = date(year, month, int(end_day))
    except ValueError as exc:
        raise BulkInstructionError("La fecha indicada no es válida.") from exc
    if end_date < start_date:
        raise BulkInstructionError("La fecha final debe ser posterior a la fecha inicial.")
    if (end_date - start_date).days > 62:
        raise BulkInstructionError("El rango máximo para un cambio masivo es de 63 días.")
    body = normalized[:date_match.start()] + " " + normalized[date_match.end():]
    if "todos" not in body:
        raise BulkInstructionError("Indica “todos” para confirmar que el cambio aplica al departamento activo.")
    times = [_parse_time(match) for match in _TIME.finditer(body)]
    if "entrada" in body:
        if len(times) != 1:
            raise BulkInstructionError("Indica una sola hora de entrada, por ejemplo “entrada para todos a las 9 am”.")
        return ParsedBulkInstruction(raw, "entry", start_date, end_date, start=times[0])
    if "salida" in body:
        if len(times) != 1:
            raise BulkInstructionError("Indica una sola hora de salida, por ejemplo “salida para todos a las 3 pm”.")
        return ParsedBulkInstruction(raw, "exit", start_date, end_date, end=times[0])
    if "horario" in body:
        if len(times) != 2:
            raise BulkInstructionError("Indica inicio y fin, por ejemplo “horario para todos de 9 am a 3 pm”.")
        if times[0] >= times[1]:
            raise BulkInstructionError("La hora de inicio debe ser anterior a la hora de fin.")
        return ParsedBulkInstruction(raw, "replace", start_date, end_date, start=times[0], end=times[1])
    raise BulkInstructionError("Indica si cambiarás la entrada, la salida o el horario completo.")


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(character for character in value if unicodedata.category(character) != "Mn")
    return re.sub(r"\s+", " ", value).strip()


def _parse_time(match: re.Match[str]) -> time:
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    suffix = (match.group(3) or "").replace(".", "").replace(" ", "")
    if minute > 59:
        raise BulkInstructionError("Los minutos deben estar entre 00 y 59.")
    if suffix:
        if not 1 <= hour <= 12:
            raise BulkInstructionError("La hora con AM/PM debe estar entre 1 y 12.")
        if suffix == "pm" and hour != 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
    elif not 0 <= hour <= 23:
        raise BulkInstructionError("La hora debe estar entre 00 y 23.")
    return time(hour, minute)
