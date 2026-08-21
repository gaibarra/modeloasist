"""Mexican federal mandatory rest days (LFT, article 74)."""
from __future__ import annotations

from datetime import date, timedelta


def official_holiday_name(target_date: date) -> str | None:
    year = target_date.year
    fixed = {
        date(year, 1, 1): "Año Nuevo",
        date(year, 5, 1): "Día del Trabajo",
        date(year, 9, 16): "Independencia de México",
        date(year, 12, 25): "Navidad",
    }
    if target_date in fixed:
        return fixed[target_date]
    if target_date == _nth_weekday(year, 2, 0, 1):
        return "Conmemoración de la Constitución"
    if target_date == _nth_weekday(year, 3, 0, 3):
        return "Conmemoración del natalicio de Benito Juárez"
    if target_date == _nth_weekday(year, 11, 0, 3):
        return "Conmemoración de la Revolución Mexicana"
    if year >= 2024 and (year - 2024) % 6 == 0 and target_date == date(year, 10, 1):
        return "Transmisión del Poder Ejecutivo Federal"
    return None


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    current = date(year, month, 1)
    current += timedelta(days=(weekday - current.weekday()) % 7)
    return current + timedelta(days=7 * (occurrence - 1))
