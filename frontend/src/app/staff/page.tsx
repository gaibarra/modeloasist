import Link from "next/link";
import { ChangePasswordLink } from "@/components/change-password-link";
import { InstitutionHeader } from "@/components/institution-header";
import { LogoutButton } from "@/components/logout-button";
import { PeriodDateRangeFields } from "@/components/period-date-range-fields";
import { StaffIndividualFilters } from "@/components/staff-individual-filters";
import { StaffPrintLauncher } from "@/components/staff-print-launcher";
import { StaffScheduleEditor } from "@/components/staff-schedule-editor";
import {
  DepartmentSummary,
  StaffDefaultWeek,
  StaffDepartmentEmployeeSummary,
  StaffEmployeeYearWeek,
  StaffEmployeeYearWeekDay,
  StaffEmployeeYearSummary,
  StaffMobilePeriodDay,
  StaffMobilePeriodRow,
  StaffScheduleInterval,
} from "@/lib/auth";
import { fetchBackendJson, requireStaffUser } from "@/lib/server-session";

type StaffSearchParams = {
  view?: string;
  department_id?: string;
  start_date?: string;
  end_date?: string;
  employee_id?: string;
  weeks?: string;
};

type StaffPageProps = {
  searchParams?: Promise<StaffSearchParams>;
};

type StaffView = "period" | "individual";

const formatTime = (value: string | null) => (value ? value.slice(0, 5) : "—");
const formatCompactDateWithWeekday = (value: string) => {
  const parsed = parseLocalDate(value);
  if (!parsed) {
    return value;
  }
  const weekday = parsed.toLocaleDateString("es-MX", { weekday: "short" }).replace(".", "");
  const day = String(parsed.getDate());
  const month = parsed
    .toLocaleDateString("es-MX", { month: "short" })
    .replace(".", "")
    .toUpperCase();
  return `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)} ${day}-${month}`;
};

const formatShortDateLabel = (value: string) => {
  const parsed = parseLocalDate(value);
  if (!parsed) {
    return value;
  }
  const day = String(parsed.getDate()).padStart(2, "0");
  const month = parsed
    .toLocaleDateString("es-MX", { month: "short" })
    .replace(".", "")
    .toUpperCase();
  return `${day} ${month}`;
};

const formatWeekdayChipLabel = (value: string) => {
  const parsed = parseLocalDate(value);
  if (!parsed) {
    return value;
  }
  const weekday = parsed.toLocaleDateString("es-MX", { weekday: "short" }).replace(".", "");
  return `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)}`;
};

function parseLocalDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  const parsed = new Date(year, month, day);
  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getFullYear() != year ||
    parsed.getMonth() != month ||
    parsed.getDate() != day
  ) {
    return null;
  }
  return parsed;
}

function validatePeriodRange(startDate: string, endDate: string) {
  const start = parseLocalDate(startDate);
  const end = parseLocalDate(endDate);
  if (!start || !end) {
    return "Captura fechas válidas para consultar el periodo.";
  }
  if (start > end) {
    return "La fecha de inicio no puede ser posterior a la fecha final.";
  }
  if (start.getDay() !== 1 || end.getDay() !== 0) {
    return "El periodo debe iniciar en lunes y terminar en domingo.";
  }
  return null;
}

function getDefaultPreviousWeekRange() {
  const today = new Date();
  const normalizedToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const currentWeekMonday = new Date(normalizedToday);
  currentWeekMonday.setDate(normalizedToday.getDate() - ((normalizedToday.getDay() + 6) % 7));
  const previousWeekMonday = new Date(currentWeekMonday);
  previousWeekMonday.setDate(currentWeekMonday.getDate() - 7);
  const previousWeekSunday = new Date(previousWeekMonday);
  previousWeekSunday.setDate(previousWeekMonday.getDate() + 6);

  return {
    startDate: previousWeekMonday.toISOString().slice(0, 10),
    endDate: previousWeekSunday.toISOString().slice(0, 10),
  };
}

async function fetchDefaultWeekRange() {
  try {
    const payload = await fetchBackendJson<StaffDefaultWeek>("/staff/mobile/default-week");
    return {
      startDate: payload.start_date,
      endDate: payload.end_date,
    };
  } catch {
    return getDefaultPreviousWeekRange();
  }
}

async function fetchDepartments() {
  return fetchBackendJson<DepartmentSummary[]>("/staff/departments");
}

async function fetchPeriodAttendance(departmentId: number, startDate: string, endDate: string) {
  return fetchBackendJson<StaffMobilePeriodRow[]>(
    `/staff/mobile/daily?department_id=${departmentId}&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
  );
}

async function fetchDepartmentEmployees(departmentId: number) {
  return fetchBackendJson<StaffDepartmentEmployeeSummary[]>(`/staff/mobile/employees?department_id=${departmentId}`);
}

async function fetchEmployeeYearSummary(departmentId: number, employeeId: number, weeks: number) {
  return fetchBackendJson<StaffEmployeeYearSummary>(
    `/staff/mobile/employee-year?department_id=${departmentId}&employee_id=${employeeId}&weeks=${weeks}`,
  );
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatScheduleRange(start: string | null, end: string | null) {
  if (!start && !end) {
    return "Sin horario";
  }
  return `${formatTime(start)} - ${formatTime(end)}`;
}

function formatScheduleIntervals(intervals: StaffScheduleInterval[], fallbackStart?: string | null, fallbackEnd?: string | null) {
  if (intervals.length > 0) {
    return intervals.map((interval) => `${formatTime(interval.start)} - ${formatTime(interval.end)}`).join(" | ");
  }
  return formatScheduleRange(fallbackStart ?? null, fallbackEnd ?? null);
}

function formatCompactScheduleIntervals(intervals: StaffScheduleInterval[], fallbackStart?: string | null, fallbackEnd?: string | null) {
  if (intervals.length > 0) {
    return intervals.map((interval) => `${formatTime(interval.start)}–${formatTime(interval.end)}`).join(" · ");
  }
  if (!fallbackStart && !fallbackEnd) {
    return "Sin horario";
  }
  return `${formatTime(fallbackStart ?? null)}–${formatTime(fallbackEnd ?? null)}`;
}

function getWeekdayOrderIndex(value: string) {
  const parsed = parseLocalDate(value);
  if (!parsed) {
    return null;
  }
  return parsed.getDay();
}

function getWeekdayShortLabelFromIndex(index: number) {
  return ["DOM", "LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB"][index] ?? "—";
}

function buildWeekdayScheduleSummaries(summary: StaffEmployeeYearSummary) {
  const grouped = new Map<number, { latest: string; values: Set<string> }>();

  for (const week of summary.weeks) {
    for (const day of week.days) {
      const weekdayIndex = getWeekdayOrderIndex(day.date);
      const scheduleLabel = formatCompactScheduleIntervals(day.schedule_intervals, day.scheduled_start, day.scheduled_end);

      if (weekdayIndex === null || scheduleLabel === "Sin horario") {
        continue;
      }

      const current = grouped.get(weekdayIndex);
      if (!current) {
        grouped.set(weekdayIndex, { latest: scheduleLabel, values: new Set([scheduleLabel]) });
        continue;
      }

      current.values.add(scheduleLabel);
    }
  }

  return [1, 2, 3, 4, 5, 6, 0]
    .filter((weekdayIndex) => grouped.has(weekdayIndex))
    .map((weekdayIndex) => {
      const entry = grouped.get(weekdayIndex)!;
      const variants = Array.from(entry.values).sort();
      return {
        weekdayIndex,
        label: getWeekdayShortLabelFromIndex(weekdayIndex),
        schedule: entry.latest,
        isVariable: entry.values.size > 1,
        variants,
      };
    });
}

function getDayScheduleSummary(day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay) {
  const summary = formatCompactScheduleIntervals(day.schedule_intervals, day.scheduled_start, day.scheduled_end);
  if (summary === "Sin horario") {
    return null;
  }
  return summary;
}

function getAbsenceEventDetail(day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay) {
  if (day.status !== "absence") {
    return null;
  }

  if (day.entry_event && !day.exit_event) {
    return `${formatTime(day.entry_event)} · faltó salida`;
  }

  if (!day.entry_event && day.exit_event) {
    return `${formatTime(day.exit_event)} · faltó entrada`;
  }

  const singleEvent = day.entry_event ?? day.exit_event;
  return singleEvent ? `${formatTime(singleEvent)} · marca única` : null;
}

function countAbsenceDays(summary: StaffEmployeeYearSummary) {
  return summary.weeks.reduce(
    (total, week) => total + week.days.filter((day) => day.status === "absence").length,
    0,
  );
}

function countLateDays(days: Array<StaffMobilePeriodDay | StaffEmployeeYearWeekDay>) {
  return days.filter((day) => day.status === "late").length;
}

function countAbsenceStatuses(days: Array<StaffMobilePeriodDay | StaffEmployeeYearWeekDay>) {
  return days.filter((day) => day.status === "absence").length;
}

function formatEntryExitSummary(
  entryEvent: string | null,
  exitEvent: string | null,
  entryEventInferred: boolean,
  exitEventInferred: boolean,
) {
  const entryLabel = `${formatTime(entryEvent)}${entryEventInferred ? " · inf." : ""}`;
  const exitLabel = `${formatTime(exitEvent)}${exitEventInferred ? " · inf." : ""}`;
  return `${entryLabel} / ${exitLabel}`;
}

function getDaySummaryValue(day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay) {
  if (day.status === "absence") {
    return "Falta";
  }
  const hasAnyMark = Boolean(day.entry_event) || Boolean(day.exit_event) || day.total_events > 0;
  if (hasAnyMark) {
    return formatEntryExitSummary(day.entry_event, day.exit_event, day.entry_event_inferred, day.exit_event_inferred);
  }
  return "X";
}

function getDaySummaryClasses(day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay) {
  if (day.status === "absence") {
    return {
      container: "border-rose-200 bg-rose-50/90 hover:bg-rose-100/80",
      label: "text-rose-700",
      value: "font-extrabold text-rose-800",
    };
  }
  if (day.status === "on_time" && day.total_events > 0) {
    return {
      container: "border-emerald-200 bg-emerald-50/90 hover:bg-emerald-100/80",
      label: "text-emerald-700",
      value: "font-extrabold text-emerald-800",
    };
  }
  if (day.status === "late" || day.status === "left_early") {
    return {
      container: "border-amber-200 bg-amber-50/90 hover:bg-amber-100/80",
      label: "text-amber-700",
      value: "font-bold text-amber-800",
    };
  }
  return {
    container: "border-slate-200 bg-slate-50/85 hover:bg-slate-100/85",
    label: "text-slate-600",
    value: "font-semibold text-slate-700",
  };
}

function normalizeView(value?: string): StaffView {
  return value === "individual" ? "individual" : "period";
}

function buildHref(
  pathname: string,
  currentParams: StaffSearchParams,
  overrides: Record<string, string | number | null | undefined> = {},
) {
  const search = new URLSearchParams();
  const merged: Record<string, string | number | null | undefined> = {
    ...currentParams,
    ...overrides,
  };

  for (const [key, value] of Object.entries(merged)) {
    if (value === null || value === undefined || value === "") {
      continue;
    }
    search.set(key, String(value));
  }

  const query = search.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function buildStaffHref(
  currentParams: StaffSearchParams,
  overrides: Record<string, string | number | null | undefined> = {},
) {
  return buildHref("/staff", currentParams, overrides);
}

function buildStaffPrintHref(
  currentParams: StaffSearchParams,
  overrides: Record<string, string | number | null | undefined> = {},
) {
  return buildHref("/staff/print", currentParams, overrides);
}

export default async function StaffMobilePage({ searchParams }: StaffPageProps) {
  const [user, resolvedSearchParams] = await Promise.all([requireStaffUser(), searchParams]);
  const params = resolvedSearchParams ?? {};
  const view = normalizeView(params.view);
  const [departments, defaultRange] = await Promise.all([fetchDepartments(), fetchDefaultWeekRange()]);
  const defaultDepartmentId = departments[0]?.id ?? null;

  const requestedDepartmentId = Number(params.department_id ?? defaultDepartmentId ?? 0) || 0;
  const selectedDepartment = departments.find((department) => department.id === requestedDepartmentId) ?? departments[0] ?? null;
  const selectedDepartmentId = selectedDepartment?.id ?? 0;
  const selectedEmployeeId = Number(params.employee_id ?? 0) || 0;
  const selectedWeeks = [2, 3, 4, 6, 8, 12].includes(Number(params.weeks)) ? Number(params.weeks) : 4;
  const startDate = params.start_date ?? defaultRange.startDate;
  const endDate = params.end_date ?? defaultRange.endDate;

  const validationError = view === "period" ? validatePeriodRange(startDate, endDate) : null;
  const rows = view === "period" && selectedDepartmentId > 0 && !validationError
    ? await fetchPeriodAttendance(selectedDepartmentId, startDate, endDate)
    : [];
  const departmentEmployees = view === "individual" && selectedDepartmentId > 0
    ? await fetchDepartmentEmployees(selectedDepartmentId)
    : [];
  const hasSelectedEmployee = departmentEmployees.some((employee) => employee.id === selectedEmployeeId);
  const employeeYearSummary = view === "individual" && selectedDepartmentId > 0 && hasSelectedEmployee
    ? await fetchEmployeeYearSummary(selectedDepartmentId, selectedEmployeeId, selectedWeeks)
    : null;
  const weekdayScheduleSummaries = employeeYearSummary ? buildWeekdayScheduleSummaries(employeeYearSummary) : [];
  const absenceDays = employeeYearSummary ? countAbsenceDays(employeeYearSummary) : 0;

  const totalEvents = rows.reduce((sum, row) => sum + row.total_events, 0);
  const totalRegisteredDays = rows.reduce((sum, row) => sum + row.active_days, 0);
  const totalLateDays = rows.reduce((sum, row) => sum + countLateDays(row.days), 0);
  const totalAbsenceDays = rows.reduce((sum, row) => sum + countAbsenceStatuses(row.days), 0);
  const selectedDepartmentLabel = selectedDepartment
    ? `${selectedDepartment.campus ? `${selectedDepartment.campus} · ` : ""}${selectedDepartment.name}`
    : "Sin selección";
  const periodSwitchHref = buildStaffHref(params, { view: "period" });
  const individualSwitchHref = buildStaffHref(params, { view: "individual" });
  const periodPrintHref = buildStaffPrintHref(params, {
    view: "period",
    department_id: selectedDepartmentId,
    start_date: startDate,
    end_date: endDate,
  });
  const individualPrintHref = buildStaffPrintHref(params, {
    view: "individual",
    department_id: selectedDepartmentId,
    employee_id: selectedEmployeeId,
  });

  return (
    <div className="page-shell text-foreground">
      <div className="mx-auto flex max-w-5xl flex-col gap-5">
        <InstitutionHeader
          eyebrow="Consulta de asistencia"
          title={user.full_name}
          titleClassName="!text-lg sm:!text-xl"
          details={
            <>
              <div className="surface-subtle rounded-full px-3 py-1.5 text-xs font-semibold text-(--color-brand-strong)">
                Staff operativo
              </div>
              {selectedDepartment ? (
                <div className="surface-subtle rounded-full px-3 py-1.5 text-xs font-semibold text-(--color-brand-strong)">
                  Departamento activo: {selectedDepartmentLabel}
                </div>
              ) : null}
            </>
          }
          compact
          actions={<><ChangePasswordLink />{user.is_superadmin ? <Link href="/staff/admin" className="secondary-button">Gestionar staff</Link> : null}<LogoutButton /></>}
        />

        <div className="flex justify-center">
          <div className="brand-panel inline-flex w-full max-w-lg items-center justify-center gap-2 rounded-[1.6rem] border-[1.5px] border-(--color-brand-soft) bg-[linear-gradient(180deg,rgba(230,237,247,0.92),rgba(255,255,255,0.98))] p-2.5 shadow-[0_18px_36px_-28px_rgba(15,39,71,0.45)]">
            <Link
              href={periodSwitchHref}
              aria-current={view === "period" ? "page" : undefined}
              className={`flex-1 rounded-2xl px-6 py-3.5 text-center text-sm font-bold transition duration-200 ${
                view === "period"
                  ? "bg-(--color-brand) text-white shadow-[0_14px_24px_-18px_rgba(15,39,71,0.9)] ring-1 ring-(--color-brand-strong)"
                  : "bg-white/72 text-(--color-brand) hover:bg-white hover:text-(--color-brand-strong) hover:shadow-sm"
              }`}
            >
              Periodo
            </Link>
            <Link
              href={individualSwitchHref}
              aria-current={view === "individual" ? "page" : undefined}
              className={`flex-1 rounded-2xl px-6 py-3.5 text-center text-sm font-bold transition duration-200 ${
                view === "individual"
                  ? "bg-(--color-brand) text-white shadow-[0_14px_24px_-18px_rgba(15,39,71,0.9)] ring-1 ring-(--color-brand-strong)"
                  : "bg-white/72 text-(--color-brand) hover:bg-white hover:text-(--color-brand-strong) hover:shadow-sm"
              }`}
            >
              Individual
            </Link>
          </div>
        </div>

        {departments.length === 0 ? (
          <section className="surface-card border-dashed p-6 text-sm text-(--muted) shadow-none">
            No hay departamentos disponibles para tu cuenta en este momento.
          </section>
        ) : view === "period" ? (
          <>
            <section className="surface-card p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="section-eyebrow">Consulta por semana</p>
                  <h2 className="mt-1 text-lg font-semibold text-(--color-brand-strong)">Periodo semanal por departamento</h2>
                </div>
                {rows.length > 0 && !validationError ? (
                  <StaffPrintLauncher href={periodPrintHref} label="Imprimir periodo" />
                ) : null}
              </div>

              <form className="mt-4 grid gap-3 lg:grid-cols-[1.4fr_1fr_1fr_auto]">
                <input type="hidden" name="view" value="period" />
                <label className="space-y-2 text-sm font-medium text-foreground">
                  Departamento
                  <select
                    name="department_id"
                    defaultValue={selectedDepartmentId > 0 ? String(selectedDepartmentId) : ""}
                    className="field-input"
                  >
                    {departments.map((department) => (
                      <option key={department.id} value={department.id}>
                        {department.campus ? `${department.campus} · ` : ""}
                        {department.name}
                      </option>
                    ))}
                  </select>
                </label>
                <PeriodDateRangeFields startDate={startDate} endDate={endDate} />
                <button
                  type="submit"
                  className="primary-button mt-auto px-5 py-3 text-sm"
                >
                  Consultar
                </button>
              </form>
            </section>

            <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <article className="surface-card p-4">
                <p className="section-eyebrow">Departamento</p>
                <p className="mt-2 text-sm font-semibold text-(--color-brand-strong)">{selectedDepartmentLabel}</p>
              </article>
              <article className="surface-card p-4">
                <p className="section-eyebrow">Periodo consultado</p>
                <p className="mt-2 text-sm font-semibold text-(--color-brand-strong)">{startDate} → {endDate}</p>
              </article>
              <article className="surface-card p-4">
                <p className="section-eyebrow">Colaboradores</p>
                <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{rows.length}</p>
              </article>
              <article className="surface-card p-4">
                <p className="section-eyebrow">Días registrados</p>
                <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{totalRegisteredDays}</p>
              </article>
              <article className="surface-card p-4">
                <p className="section-eyebrow">Retardos</p>
                <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{totalLateDays}</p>
              </article>
              <article className="surface-card p-4">
                <p className="section-eyebrow">Faltas</p>
                <p className="mt-2 text-2xl font-semibold text-rose-700">{totalAbsenceDays}</p>
              </article>
              <article className="surface-card p-4">
                <p className="section-eyebrow">Eventos acumulados</p>
                <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{totalEvents}</p>
              </article>
            </section>

            <section className="space-y-3">
              {validationError ? (
                <div className="rounded-3xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 shadow-sm">
                  {validationError}
                </div>
              ) : null}

              {rows.length === 0 ? (
                <div className="surface-card border-dashed p-6 text-sm text-(--muted)">
                  {validationError
                    ? "Ajusta el rango y vuelve a consultar."
                    : "No hay colaboradores o registros para este departamento en el periodo seleccionado."}
                </div>
              ) : (
                rows.map((row) => <PeriodAttendanceRow key={`${row.employee_id}-${row.period_start}-${row.period_end}`} row={row} />)
              )}
            </section>
          </>
        ) : (
          <>
            <section className="brand-panel p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-1">
                  <p className="section-eyebrow">Consulta individual</p>
                  {/* <h2 className="text-lg font-semibold text-(--color-brand-strong)">Resumen acumulado por colaborador</h2> */}
                  {/* <p className="text-sm text-(--muted)">
                    Revisa el acumulado anual hasta el cierre de la semana anterior y compara cada semana contra el horario registrado.
                  </p> */}
                </div>
                {employeeYearSummary ? (
                  <StaffPrintLauncher
                    href={individualPrintHref}
                    label="Imprimir individual"
                    className="secondary-button inline-flex items-center gap-2 px-4 py-2 text-sm"
                  />
                ) : null}
              </div>

              <StaffIndividualFilters
                departments={departments}
                selectedDepartmentId={selectedDepartmentId}
                selectedEmployeeId={hasSelectedEmployee ? selectedEmployeeId : null}
                departmentEmployees={departmentEmployees}
                selectedWeeks={selectedWeeks}
              />

              <div className="alert-info mt-4">
                {employeeYearSummary
                  ? `Ventana consultada: ${employeeYearSummary.window_start} → ${employeeYearSummary.window_end}.`
                  : `Selecciona un colaborador para consultar el acumulado desde 2026-01-01 hasta ${defaultRange.endDate}.`}
              </div>

              {!hasSelectedEmployee && selectedEmployeeId > 0 ? (
                <div className="alert-warning mt-4">
                  El colaborador seleccionado no pertenece al departamento activo.
                </div>
              ) : null}

              {departmentEmployees.length === 0 ? (
                <div className="surface-muted mt-4 border-dashed p-4 text-sm text-(--muted)">
                  Aún no hay colaboradores disponibles en el departamento seleccionado.
                </div>
              ) : null}
            </section>

            {employeeYearSummary ? (
              <>
                <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <article className="surface-card p-4">
                    <p className="section-eyebrow">Colaborador</p>
                    <p className="mt-2 text-sm font-semibold text-(--color-brand-strong)">{employeeYearSummary.employee_name}</p>
                    <p className="mt-1 text-xs text-(--muted)">{employeeYearSummary.employee_email ?? "Sin correo registrado"}</p>
                  </article>
                  <article className="surface-card p-4">
                    <p className="section-eyebrow">Días registrados</p>
                    <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{employeeYearSummary.total_days}</p>
                  </article>
                  <article className="surface-card p-4">
                    <p className="section-eyebrow">Retardos</p>
                    <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{employeeYearSummary.late_days}</p>
                  </article>
                  <article className="surface-card p-4">
                    <p className="section-eyebrow">Faltas</p>
                    <p className="mt-2 text-2xl font-semibold text-rose-700">{absenceDays}</p>
                  </article>
                  <article className="surface-card p-4">
                    <p className="section-eyebrow">Puntualidad</p>
                    <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">
                      {formatPercent(employeeYearSummary.punctuality_rate)}
                    </p>
                  </article>
                </section>

                <section className="surface-card p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-(--color-brand-strong)">{employeeYearSummary.department_name}</h3>
                      <p className="text-sm text-(--muted)">
                        {employeeYearSummary.campus ?? "Sin campus"}
                      </p>
                      {weekdayScheduleSummaries.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {weekdayScheduleSummaries.map((schedule) => (
                            <div key={schedule.weekdayIndex} className="surface-subtle rounded-2xl px-3 py-2 text-[11px] text-(--color-brand-strong)">
                              <span className="font-semibold uppercase tracking-wide text-(--muted)">{schedule.label}</span>{" "}
                              <span className="font-semibold">{schedule.schedule}</span>
                              {schedule.isVariable ? (
                                <span
                                  className="ml-1 cursor-help text-[10px] text-amber-700"
                                  title={`Horarios detectados: ${schedule.variants.join(" | ")}`}
                                >
                                  var.
                                </span>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-2 text-sm text-(--muted)">Horario: {formatScheduleIntervals(employeeYearSummary.registered_schedule_intervals)}</p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <SummaryBadge label="Semanas" value={String(employeeYearSummary.weeks.length)} />
                      <SummaryBadge
                        label="Ventana"
                        value={`${employeeYearSummary.window_start} → ${employeeYearSummary.window_end}`}
                      />
                    </div>
                  </div>
                </section>

                <section className="grid gap-4">
                  {employeeYearSummary.weeks.length === 0 ? (
                    <div className="surface-card border-dashed p-6 text-sm text-(--muted)">
                      Aún no hay semanas registradas para este colaborador.
                    </div>
                  ) : (
                    employeeYearSummary.weeks.map((week) => <WeeklyAttendanceRow key={`${week.week_start}-${week.week_end}`} week={week} />)
                  )}
                </section>
              </>
            ) : (
              <section className="surface-card border-dashed p-6 text-sm text-(--muted)">
               
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function WeeklyAttendanceRow({ week }: { week: StaffEmployeeYearWeek }) {
  return (
      <article className="surface-card p-3 transition-colors duration-200 hover:bg-slate-50/40">
        <div className="flex items-center gap-2.5">
          <div className="rounded-2xl border border-border bg-white px-3 py-2.5">
            <h3 className="text-[13px] font-semibold text-(--color-brand-strong)">{formatShortDateLabel(week.week_start)} → {formatShortDateLabel(week.week_end)}</h3>
            <p className="mt-1 text-[11px] text-(--muted)">{week.active_days} días con registros · {week.total_events} eventos</p>
          </div>

        </div>

        <div className="mt-3 grid gap-2 grid-cols-2 sm:grid-cols-4 xl:grid-cols-7">
            {week.days.map((day) => (
              <DaySummaryBadge key={`${week.week_start}-${day.date}`} day={day} />
            ))}
        </div>
      </article>
  );
}

function PeriodAttendanceRow({ row }: { row: StaffMobilePeriodRow }) {
  const rowLateDays = countLateDays(row.days);
  const rowAbsenceDays = countAbsenceStatuses(row.days);

  return (
    <article className="surface-card p-4 transition-colors duration-200 hover:bg-slate-50/40">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-base font-semibold text-(--color-brand-strong)">{row.employee_name}</h2>
          <p className="text-xs text-(--muted)">{row.employee_email ?? "Sin correo registrado"}</p>
          <p className="mt-1 text-xs text-(--muted)">{row.campus ?? "Sin campus"} · {row.department_name}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <SummaryBadge label="Días registrados" value={String(row.active_days)} />
          <SummaryBadge label="Retardos" value={String(rowLateDays)} />
          <SummaryBadge label="Faltas" value={String(rowAbsenceDays)} />
          <SummaryBadge label="Eventos" value={String(row.total_events)} />
          <StaffScheduleEditor employeeId={row.employee_id} employeeName={row.employee_name} departmentId={row.department_id} />
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2.5">
        <div className="rounded-2xl border border-border bg-white px-3 py-2.5">
          <h3 className="text-[13px] font-semibold text-(--color-brand-strong)">{formatShortDateLabel(row.period_start)} → {formatShortDateLabel(row.period_end)}</h3>
          <p className="mt-1 text-[11px] text-(--muted)">{row.active_days} días con registros · {row.total_events} eventos</p>
        </div>
      </div>

      <div className="mt-3 grid gap-2 grid-cols-2 sm:grid-cols-4 xl:grid-cols-7">
        {row.days.map((day) => (
          <DaySummaryBadge key={`${row.employee_id}-${day.date}`} day={day} />
        ))}
      </div>
    </article>
  );
}

function DaySummaryBadge({ day }: { day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay }) {
  const styles = getDaySummaryClasses(day);
  const summaryValue = getDaySummaryValue(day);
  const absenceEventDetail = getAbsenceEventDetail(day);
  const dayScheduleSummary = getDayScheduleSummary(day);

  return (
    <div
      className={`rounded-2xl border px-3 py-2 transition-colors duration-200 ${styles.container}`}
      title={formatCompactDateWithWeekday(day.date)}
    >
      <p className={`text-[10px] font-semibold uppercase tracking-wide ${styles.label}`}>{formatWeekdayChipLabel(day.date)}</p>
      <p className={`mt-1 text-sm leading-tight ${styles.value}`}>{summaryValue}</p>
      {absenceEventDetail ? (
        <p className="mt-1 text-[10px] font-semibold leading-tight text-rose-700">{absenceEventDetail}</p>
      ) : null}
      {dayScheduleSummary ? (
        <p className="mt-1 text-[10px] leading-tight text-slate-600">{dayScheduleSummary}</p>
      ) : null}
    </div>
  );
}

function SummaryBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface-subtle rounded-full px-3 py-1 text-xs font-semibold text-(--color-brand-strong)">
      {label}: {value}
    </div>
  );
}
