export type AssignmentDepartment = { id: number; name: string; campus?: string | null; is_departed?: boolean };

export function isBajaLabel(value?: string | null): boolean {
  const normalized = (value ?? "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toUpperCase().replace(/[^A-Z0-9]+/g, " ").trim();
  return /(?:^| )BAJAS(?: NOMINA)?$/.test(normalized);
}

export function isBajaDepartment(d: AssignmentDepartment): boolean {
  return d.is_departed ?? (isBajaLabel(d.name) || isBajaLabel(d.campus));
}

export function changeDepartments(ids: number[], primary: number | null, departments: AssignmentDepartment[], changed: AssignmentDepartment, checked: boolean) {
  const next = checked
    ? isBajaDepartment(changed) ? [changed.id] : [...ids.filter(id => id !== changed.id && !departments.some(d => d.id === id && isBajaDepartment(d))), changed.id]
    : ids.filter(id => id !== changed.id);
  return { department_ids: next, primary_department_id: primary !== null && next.includes(primary) ? primary : next[0] ?? null };
}
