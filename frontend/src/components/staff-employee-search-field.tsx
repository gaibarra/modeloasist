"use client";

import { Search } from "lucide-react";
import { useMemo, useRef, useState } from "react";

type StaffEmployeeOption = {
  id: number;
  name: string;
  email: string | null;
  campus: string | null;
};

type StaffEmployeeSearchFieldProps = {
  name: string;
  employees: StaffEmployeeOption[];
  selectedEmployeeId: number | null;
  placeholder?: string;
};

function buildEmployeeLabel(employee: StaffEmployeeOption) {
  return `${employee.name}${employee.campus ? ` · ${employee.campus}` : ""}`;
}

export function StaffEmployeeSearchField({
  name,
  employees,
  selectedEmployeeId,
  placeholder = "Busca un colaborador",
}: StaffEmployeeSearchFieldProps) {
  const initialSelectedLabel = selectedEmployeeId
    ? buildEmployeeLabel(employees.find((employee) => employee.id === selectedEmployeeId) ?? { id: 0, name: "", email: null, campus: null })
    : "";
  const selectedEmployee = useMemo(
    () => employees.find((employee) => employee.id === selectedEmployeeId) ?? null,
    [employees, selectedEmployeeId],
  );
  const [query, setQuery] = useState(initialSelectedLabel);
  const [selectedId, setSelectedId] = useState(selectedEmployee?.id ? String(selectedEmployee.id) : "");
  const [isOpen, setIsOpen] = useState(false);
  const blurTimeoutRef = useRef<number | null>(null);

  const filteredEmployees = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return employees;
    }

    return employees.filter((employee) => {
      const haystack = [employee.name, employee.email ?? "", employee.campus ?? ""]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [employees, query]);

  const handleSelect = (employee: StaffEmployeeOption) => {
    setQuery(buildEmployeeLabel(employee));
    setSelectedId(String(employee.id));
    setIsOpen(false);
  };

  return (
    <label className="space-y-2 text-sm font-medium text-foreground">
      Colaborador
      <input type="hidden" name={name} value={selectedId} />
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-(--muted)" />
        <input
          type="text"
          value={query}
          placeholder={placeholder}
          autoComplete="off"
          onFocus={() => {
            if (blurTimeoutRef.current !== null) {
              window.clearTimeout(blurTimeoutRef.current);
            }
            setQuery("");
            setIsOpen(true);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setSelectedId("");
            setIsOpen(true);
          }}
          onBlur={() => {
            blurTimeoutRef.current = window.setTimeout(() => {
              setIsOpen(false);
              if (!query.trim() && selectedEmployee) {
                setQuery(buildEmployeeLabel(selectedEmployee));
              }
            }, 120);
          }}
          className="field-input pl-12"
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-controls="staff-employee-search-results"
        />
        {isOpen ? (
          <div
            id="staff-employee-search-results"
            className="absolute z-20 mt-2 max-h-72 w-full overflow-y-auto rounded-2xl border border-border bg-white p-2 shadow-xl"
          >
            {filteredEmployees.length > 0 ? (
              filteredEmployees.map((employee) => {
                const isSelected = selectedId === String(employee.id);
                return (
                  <button
                    key={employee.id}
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => handleSelect(employee)}
                    className={`flex w-full flex-col rounded-xl px-3 py-2 text-left transition-colors ${
                      isSelected ? "bg-[rgba(29,78,216,0.10)]" : "hover:bg-slate-50"
                    }`}
                  >
                    <span className="text-sm font-semibold text-(--color-brand-strong)">{employee.name}</span>
                    <span className="text-xs text-(--muted)">
                      {employee.campus ?? "Sin campus"}
                      {employee.email ? ` · ${employee.email}` : ""}
                    </span>
                  </button>
                );
              })
            ) : (
              <div className="rounded-xl px-3 py-4 text-sm text-(--muted)">
                No hay coincidencias para tu búsqueda.
              </div>
            )}
          </div>
        ) : null}
      </div>
    </label>
  );
}
