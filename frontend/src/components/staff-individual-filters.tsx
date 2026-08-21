"use client";

import { usePathname, useSearchParams } from "next/navigation";

import { DepartmentSummary, StaffDepartmentEmployeeSummary } from "@/lib/auth";

import { StaffEmployeeSearchField } from "./staff-employee-search-field";

type StaffIndividualFiltersProps = {
  departments: DepartmentSummary[];
  selectedDepartmentId: number;
  selectedEmployeeId: number | null;
  departmentEmployees: StaffDepartmentEmployeeSummary[];
  selectedWeeks: number;
};

function buildIndividualHref(
  pathname: string,
  searchParams: URLSearchParams,
  departmentId: string,
  employeeId?: string,
  weeks?: string,
) {
  const nextSearchParams = new URLSearchParams(searchParams.toString());

  nextSearchParams.set("view", "individual");
  nextSearchParams.set("department_id", departmentId);
  if (weeks) nextSearchParams.set("weeks", weeks);

  if (employeeId && employeeId.trim()) {
    nextSearchParams.set("employee_id", employeeId);
  } else {
    nextSearchParams.delete("employee_id");
  }

  const query = nextSearchParams.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function StaffIndividualFilters({
  departments,
  selectedDepartmentId,
  selectedEmployeeId,
  departmentEmployees,
  selectedWeeks,
}: StaffIndividualFiltersProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const handleDepartmentChange = (nextDepartmentId: string) => {
    const parsedDepartmentId = Number(nextDepartmentId) || 0;

    if (parsedDepartmentId === selectedDepartmentId) {
      return;
    }

    window.location.assign(
      buildIndividualHref(pathname, new URLSearchParams(searchParams.toString()), nextDepartmentId, undefined, String(selectedWeeks)),
    );
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const departmentId = String(formData.get("department_id") ?? "");
    const employeeId = String(formData.get("employee_id") ?? "");
    const weeks = String(formData.get("weeks") ?? "4");

    window.location.assign(
      buildIndividualHref(pathname, new URLSearchParams(searchParams.toString()), departmentId, employeeId, weeks),
    );
  };

  return (
    <form className="mt-4 grid gap-3 lg:grid-cols-[1fr_1fr_180px_auto]" onSubmit={handleSubmit}>
      <input type="hidden" name="view" value="individual" />
      <label className="space-y-2 text-sm font-medium text-foreground">
        Departamento
        <select
          name="department_id"
          value={selectedDepartmentId > 0 ? String(selectedDepartmentId) : ""}
          className="field-input"
          onChange={(event) => handleDepartmentChange(event.target.value)}
        >
          {departments.map((department) => (
            <option key={department.id} value={department.id}>
              {department.campus ? `${department.campus} · ` : ""}
              {department.name}
            </option>
          ))}
        </select>
      </label>
      <StaffEmployeeSearchField
        key={`${selectedDepartmentId}-${departmentEmployees.length}-${selectedEmployeeId ?? 0}`}
        name="employee_id"
        employees={departmentEmployees}
        selectedEmployeeId={selectedEmployeeId}
        placeholder="Busca por nombre, correo o campus"
      />
      <label className="space-y-2 text-sm font-medium text-foreground">
        Número de semanas
        <input name="weeks" type="number" min="1" max="52" step="1" defaultValue={selectedWeeks} className="field-input" inputMode="numeric" />
      </label>
      <button
        type="submit"
        className="primary-button mt-auto px-5 py-3 text-sm"
      >
        Consultar
      </button>
    </form>
  );
}
