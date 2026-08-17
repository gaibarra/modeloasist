"""Helpers to canonicalize department names and preserve import aliases."""
from __future__ import annotations

from dataclasses import dataclass
import re

CANONICAL_CAMPUSES = ("Merida", "Montejo", "Chetumal", "Valladolid")
_LONG_DEPARTMENT_PATTERN = re.compile(
    r"^escuela\s+modelo\s*[-/]\s*(merida|m[eé]rida|montejo|chetumal|valladolid)\s*[-/]\s*(.+?)\s*$",
    re.IGNORECASE,
)
_GENERIC_PREFIX_PATTERN = re.compile(r"^escuela\s+modelo\s*[-/]\s*(.+?)\s*$", re.IGNORECASE)
_CAMPUS_DISPLAY_NAMES = {
    "merida": "Mérida",
    "mérida": "Mérida",
    "montejo": "Montejo",
    "chetumal": "Chetumal",
    "valladolid": "Valladolid",
}


@dataclass(frozen=True)
class CanonicalDepartment:
    raw_name: str
    canonical_name: str
    campus: str | None

    @property
    def aliases(self) -> tuple[str, ...]:
        if not self.raw_name:
            return ()
        if self.raw_name == self.canonical_name:
            return (self.raw_name,)
        return (self.raw_name, self.canonical_name)


def canonicalize_department(value: str | None) -> CanonicalDepartment:
    raw_name = (value or "").strip()
    if not raw_name:
        return CanonicalDepartment(raw_name="", canonical_name="", campus=None)

    match = _LONG_DEPARTMENT_PATTERN.match(raw_name)
    if match:
        campus = _CAMPUS_DISPLAY_NAMES.get(match.group(1).strip().lower())
        canonical_name = match.group(2).strip()
        return CanonicalDepartment(raw_name=raw_name, canonical_name=canonical_name, campus=campus)

    generic_match = _GENERIC_PREFIX_PATTERN.match(raw_name)
    if generic_match:
        canonical_name = generic_match.group(1).strip()
        return CanonicalDepartment(raw_name=raw_name, canonical_name=canonical_name, campus=None)

    return CanonicalDepartment(raw_name=raw_name, canonical_name=raw_name, campus=None)


def derive_department_campus(value: str | None) -> str | None:
    canonical = canonicalize_department(value)
    if canonical.campus:
        return canonical.campus
    raw_name = canonical.raw_name
    if not raw_name:
        return None
    parts = [part.strip() for part in raw_name.split("/") if part.strip()]
    if len(parts) >= 2:
        candidate = parts[1]
        if candidate in {"Mérida", "Montejo", "Chetumal", "Valladolid"}:
            return candidate
    return None