import Link from "next/link";
import { AlertTriangle, CheckCircle2, ChevronDown, Clock3, Search, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { ChangePasswordLink } from "@/components/change-password-link";
import { InstitutionHeader } from "@/components/institution-header";
import { LogoutButton } from "@/components/logout-button";
import { PeriodDateRangeFields } from "@/components/period-date-range-fields";
import { StaffIndividualFilters } from "@/components/staff-individual-filters";
import { StaffPrintLauncher } from "@/components/staff-print-launcher";
import { StaffScheduleEditor } from "@/components/staff-schedule-editor";
import { StaffScheduleBulkDialog } from "@/components/staff-schedule-bulk-dialog";
import { StaffHolidayWorkButton } from "@/components/staff-holiday-work-button";
import { StaffAttendanceExemptionDialog } from "@/components/staff-attendance-exemption-dialog";
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
  filter?: string;
  q?: string;
  sort?: string;
};

type StaffPageProps = {
  searchParams?: Promise<StaffSearchParams>;
};

type StaffView = "period" | "individual";
type PeriodFilter = "incidents" | "all" | "absence" | "late" | "justified" | "no_events";
type PeriodSort = "severity" | "name";

const PERIOD_FILTERS: Array<{ value: PeriodFilter; label: string }> = [
  { value: "incidents", label: "Solo incidencias" },
  { value: "all", label: "Todos" },
  { value: "absence", label: "Faltas" },
  { value: "late", label: "Retardos" },
  { value: "justified", label: "Justificados" },
  { value: "no_events", label: "Sin eventos" },
];

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
  const month = parsed.toLocaleDateString("es-MX", { month: "short" }).replace(".", "");
  return `${weekday.toUpperCase()} ${String(parsed.getDate()).padStart(2, "0")} ${month.toUpperCase()}`;
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

function countJustifiedStatuses(days: Array<StaffMobilePeriodDay | StaffEmployeeYearWeekDay>) {
  return days.filter((day) => ["justified", "entry_excused", "exit_excused"].includes(day.status)).length;
}

function normalizePeriodFilter(value?: string): PeriodFilter {
  return PERIOD_FILTERS.some((filter) => filter.value === value) ? value as PeriodFilter : "incidents";
}

function normalizePeriodSort(value?: string): PeriodSort {
  return value === "severity" ? "severity" : "name";
}

function hasNoEvent(day: StaffMobilePeriodDay) {
  return day.status === "no_events" && day.total_events === 0;
}

function hasIncident(day: StaffMobilePeriodDay) {
  // Sin marcas también requiere revisión: puede convertirse en una exención,
  // una carga pendiente o, tras el margen aplicable, una falta calculada.
  return hasNoEvent(day) || ["absence", "late", "left_early", "justified", "entry_excused", "exit_excused"].includes(day.status);
}

function matchesPeriodFilter(row: StaffMobilePeriodRow, filter: PeriodFilter) {
  if (filter === "all") return true;
  if (filter === "incidents") return row.days.some(hasIncident);
  if (filter === "absence") return row.days.some((day) => day.status === "absence");
  if (filter === "late") return row.days.some((day) => day.status === "late" || day.status === "left_early");
  if (filter === "justified") return row.days.some((day) => ["justified", "entry_excused", "exit_excused"].includes(day.status));
  return row.days.some(hasNoEvent);
}

function getRowSeverity(row: StaffMobilePeriodRow) {
  return row.days.reduce((score, day) => score + (
    day.status === "absence" ? 100 :
    day.status === "late" || day.status === "left_early" ? 10 :
    hasIncident(day) ? 1 : 0
  ), 0);
}

function getRowHeadline(row: StaffMobilePeriodRow) {
  const absences = countAbsenceStatuses(row.days);
  const late = row.days.filter((day) => day.status === "late" || day.status === "left_early").length;
  const justified = countJustifiedStatuses(row.days);
  if (absences) return `${absences} ${absences === 1 ? "falta" : "faltas"}`;
  if (late) return `${late} ${late === 1 ? "incidencia de horario" : "incidencias de horario"}`;
  if (justified) {
    const homeOffice = row.days.some((day) => day.exemption_reason === "home_office");
    return homeOffice ? "Home office" : `${justified} ${justified === 1 ? "justificado" : "justificados"}`;
  }
  return "Sin incidencias";
}

function getRowHeadlineClass(row: StaffMobilePeriodRow) {
  if (row.days.some((day) => day.status === "absence")) return "bg-rose-100 text-rose-800";
  if (row.days.some((day) => day.status === "late" || day.status === "left_early")) return "bg-amber-100 text-amber-800";
  if (row.days.some((day) => ["justified", "entry_excused", "exit_excused"].includes(day.status))) return "bg-sky-100 text-sky-800";
  return "bg-emerald-100 text-emerald-800";
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
  if (day.status === "justified") return "Justificado";
  if (day.status === "entry_excused") return "Entrada justificada";
  if (day.status === "exit_excused") return "Salida justificada";
  if (day.status === "official_holiday") {
    return "Descanso";
  }
  if (day.status === "absence") {
    return "Falta";
  }
  const hasAnyMark = Boolean(day.entry_event) || Boolean(day.exit_event) || day.total_events > 0;
  if (hasAnyMark) {
    return formatEntryExitSummary(day.entry_event, day.exit_event, day.entry_event_inferred, day.exit_event_inferred);
  }
  return "X";
}

function formatExemptionReason(reason: string | null) {
  const labels: Record<string, string> = {
    incapacidad: "Incapacidad",
    comision_institucional: "Comisión institucional",
    permiso_staff: "Permiso de staff",
    fuerza_mayor: "Fuerza mayor",
    home_office: "Home office",
    otro: "Otro",
  };
  return reason ? labels[reason] ?? reason : null;
}

function getDaySummaryClasses(day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay) {
  if (["justified", "entry_excused", "exit_excused"].includes(day.status)) {
    return { container: "border-sky-200 bg-sky-50/90 hover:bg-sky-100/80", label: "text-sky-700", value: "font-extrabold text-sky-800" };
  }
  if (day.status === "official_holiday") {
    return {
      container: "border-violet-200 bg-violet-50/90 hover:bg-violet-100/80",
      label: "text-violet-700",
      value: "font-extrabold text-violet-800",
    };
  }
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

function PeriodFilterNavigation({ currentParams, activeFilter }: { currentParams: StaffSearchParams; activeFilter: PeriodFilter }) {
  return (
    <nav className="flex flex-wrap gap-2" aria-label="Filtrar colaboradores">
      {PERIOD_FILTERS.map((filter) => {
        const active = filter.value === activeFilter;
        return <Link
          key={filter.value}
          href={buildStaffHref(currentParams, { view: "period", filter: filter.value })}
          aria-current={active ? "page" : undefined}
          className={`min-h-11 rounded-full px-3 py-2 text-xs font-bold transition ${active ? "bg-(--color-brand) text-white shadow-sm" : "border border-border bg-white text-(--color-brand) hover:border-(--color-brand-soft) hover:bg-(--color-brand-tint)"}`}
        >
          {filter.label}
        </Link>;
      })}
    </nav>
  );
}

function PeriodMetricLink({ label, value, href, tone = "default" }: { label: string; value: string; href: string; tone?: "default" | "danger" | "warning" | "info" }) {
  const valueClass = tone === "danger" ? "text-rose-700" : tone === "warning" ? "text-amber-700" : tone === "info" ? "text-sky-700" : "text-(--color-brand-strong)";
  return <Link href={href} className="surface-card min-h-28 p-4 transition hover:-translate-y-0.5 hover:border-(--color-brand-soft) hover:shadow-md focus:outline-none focus:ring-4 focus:ring-(--color-brand-tint)">
    <p className="section-eyebrow">{label}</p>
    <p className={`mt-2 text-2xl font-semibold ${valueClass}`}>{value}</p>
  </Link>;
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
  const requestedWeeks = Number(params.weeks);
  const selectedWeeks = Number.isInteger(requestedWeeks) && requestedWeeks >= 1 && requestedWeeks <= 52 ? requestedWeeks : 4;
  const activePeriodFilter = normalizePeriodFilter(params.filter);
  const activePeriodSort = normalizePeriodSort(params.sort);
  const searchQuery = (params.q ?? "").trim();
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
  const totalJustifiedDays = rows.reduce((sum, row) => sum + countJustifiedStatuses(row.days), 0);
  const visibleRows = rows
    .filter((row) => matchesPeriodFilter(row, activePeriodFilter))
    .filter((row) => !searchQuery || `${row.employee_name} ${row.employee_email ?? ""}`.toLocaleLowerCase("es-MX").includes(searchQuery.toLocaleLowerCase("es-MX")))
    .sort((left, right) => activePeriodSort === "name"
      ? left.employee_name.localeCompare(right.employee_name, "es-MX")
      : getRowSeverity(right) - getRowSeverity(left) || left.employee_name.localeCompare(right.employee_name, "es-MX"));
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
      <div className="mx-auto flex max-w-6xl flex-col gap-5">
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
            <section className="brand-panel p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="section-eyebrow">Monitor de incidencias</p>
                  <h2 className="mt-1 text-lg font-semibold text-(--color-brand-strong)">Asistencia por departamento</h2>
                  <p className="mt-1 text-sm text-(--muted)">{selectedDepartmentLabel} · {formatShortDateLabel(startDate)} → {formatShortDateLabel(endDate)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {selectedDepartmentId > 0 ? <StaffScheduleBulkDialog departmentId={selectedDepartmentId} departmentName={selectedDepartmentLabel} /> : null}
                  {rows.length > 0 && !validationError ? (
                    <StaffPrintLauncher href={periodPrintHref} label="Imprimir periodo" />
                  ) : null}
                </div>
              </div>

              <form className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-[1.4fr_1fr_1fr_1fr_auto]">
                <input type="hidden" name="view" value="period" />
                <input type="hidden" name="filter" value={activePeriodFilter} />
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
                <label className="space-y-2 text-sm font-medium text-foreground">
                  Buscar
                  <span className="relative block">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-(--muted)" aria-hidden="true" />
                    <input name="q" defaultValue={searchQuery} className="field-input pl-9" placeholder="Nombre o correo" />
                  </span>
                </label>
                <label className="space-y-2 text-sm font-medium text-foreground">
                  Ordenar por
                  <select name="sort" defaultValue={activePeriodSort} className="field-input">
                    <option value="name">Nombre</option>
                    <option value="severity">Severidad</option>
                  </select>
                </label>
                <button
                  type="submit"
                  className="primary-button mt-auto min-h-12 px-5 py-3 text-sm"
                >
                  Consultar
                </button>
                <button
                  type="submit"
                  formAction="/staff/hours"
                  className="ghost-button min-h-12 px-5 py-3 text-sm xl:col-span-2"
                >
                  Reporte de horas semanal
                </button>
                <Link href={`/staff/contracts?department_id=${selectedDepartmentId}`} className="ghost-button min-h-12 px-5 py-3 text-sm xl:col-span-2">Contratos y horarios pendientes</Link>
              </form>
              <div className="mt-4 hidden items-center justify-between gap-3 lg:flex">
                <PeriodFilterNavigation currentParams={params} activeFilter={activePeriodFilter} />
                {(activePeriodFilter !== "incidents" || searchQuery || activePeriodSort !== "name") ? <Link href={buildStaffHref(params, { filter: null, q: null, sort: null })} className="ghost-button min-h-11 px-3 text-xs">Limpiar filtros</Link> : null}
              </div>
              <details className="mt-4 rounded-2xl border border-border bg-white p-3 lg:hidden">
                <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between text-sm font-bold text-(--color-brand-strong)"><span className="inline-flex items-center gap-2"><SlidersHorizontal className="h-4 w-4" aria-hidden="true" />Filtros de resultados</span><ChevronDown className="h-4 w-4" aria-hidden="true" /></summary>
                <div className="mt-3"><PeriodFilterNavigation currentParams={params} activeFilter={activePeriodFilter} /></div>
                {(activePeriodFilter !== "incidents" || searchQuery || activePeriodSort !== "name") ? <Link href={buildStaffHref(params, { filter: null, q: null, sort: null })} className="ghost-button mt-3 min-h-11 px-3 text-xs">Limpiar filtros</Link> : null}
              </details>
            </section>

            <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6" aria-label="Indicadores del periodo">
              <PeriodMetricLink label="Colaboradores" value={String(rows.length)} href={buildStaffHref(params, { view: "period", filter: "all" })} />
              <PeriodMetricLink label="Días registrados" value={String(totalRegisteredDays)} href={buildStaffHref(params, { view: "period", filter: "all" })} />
              <PeriodMetricLink label="Retardos" value={String(totalLateDays)} tone="warning" href={buildStaffHref(params, { view: "period", filter: "late" })} />
              <PeriodMetricLink label="Faltas" value={String(totalAbsenceDays)} tone="danger" href={buildStaffHref(params, { view: "period", filter: "absence" })} />
              <PeriodMetricLink label="Justificados" value={String(totalJustifiedDays)} tone="info" href={buildStaffHref(params, { view: "period", filter: "justified" })} />
              <PeriodMetricLink label="Eventos" value={String(totalEvents)} href={buildStaffHref(params, { view: "period", filter: "all" })} />
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
              ) : visibleRows.length === 0 ? (
                <div className="surface-card border-dashed p-6 text-sm text-(--muted)">
                  <p>No hay colaboradores que coincidan con los filtros actuales.</p>
                  <Link href={buildStaffHref(params, { view: "period", filter: "all", q: null })} className="ghost-button mt-4 min-h-11 px-3 text-xs">
                    Ver toda la plantilla
                  </Link>
                </div>
              ) : (
                <>
                  <p className="px-1 text-sm text-(--muted)" role="status">
                    Mostrando {visibleRows.length} de {rows.length} colaboradores · {PERIOD_FILTERS.find((filter) => filter.value === activePeriodFilter)?.label.toLocaleLowerCase("es-MX")}
                  </p>
                  {visibleRows.map((row) => <PeriodAttendanceRow key={`${row.employee_id}-${row.period_start}-${row.period_end}`} row={row} />)}
                </>
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
                <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
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
                    <p className="section-eyebrow">Justificados</p>
                    <p className="mt-2 text-2xl font-semibold text-sky-700">{employeeYearSummary.justified_days}</p>
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
  const rowJustifiedDays = countJustifiedStatuses(row.days);
  const headline = getRowHeadline(row);
  const headlineClass = getRowHeadlineClass(row);

  return (
    <article className="surface-card overflow-visible p-0 transition-shadow duration-200 hover:shadow-md">
      <header className="grid gap-4 border-b border-border bg-slate-50/70 p-4 xl:grid-cols-[minmax(15rem,1fr)_minmax(20rem,auto)_auto] xl:items-center">
        <div className="min-w-0">
          <p className="section-eyebrow">Colaborador</p>
          <h2 className="mt-1 truncate text-base font-semibold text-(--color-brand-strong)">{row.employee_name}</h2>
          <p className="truncate text-xs text-(--muted)">{row.employee_email ?? "Sin correo registrado"}</p>
          <p className="mt-1 text-xs text-(--muted)">{row.campus ?? "Sin campus"} · {row.department_name}</p>
          <p className="mt-2 text-xs font-semibold text-(--color-brand-strong)">{formatShortDateLabel(row.period_start)} → {formatShortDateLabel(row.period_end)}</p>
        </div>

        <div className="flex flex-col gap-2 xl:items-end">
          <span className={`inline-flex min-h-8 items-center rounded-full px-3 py-1 text-xs font-extrabold ${headlineClass}`}>
            {rowAbsenceDays ? <AlertTriangle className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" /> : rowLateDays ? <Clock3 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" /> : rowJustifiedDays ? <ShieldCheck className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" /> : <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />}
            {headline}
          </span>
          <div className="flex flex-wrap gap-1.5 xl:justify-end" aria-label={`Resumen de ${row.employee_name}`}>
            <SummaryBadge label="Días" value={String(row.active_days)} />
            <SummaryBadge label="Retardos" value={String(rowLateDays)} />
            <SummaryBadge label="Faltas" value={String(rowAbsenceDays)} />
            <SummaryBadge label="Justificados" value={String(rowJustifiedDays)} />
            <SummaryBadge label="Eventos" value={String(row.total_events)} />
          </div>
        </div>

        <div className="relative flex flex-wrap items-center gap-2 xl:justify-end">
          <StaffScheduleEditor employeeId={row.employee_id} employeeName={row.employee_name} departmentId={row.department_id} />
          <details className="relative">
            <summary className="secondary-button flex min-h-11 cursor-pointer list-none items-center gap-1.5 px-3 text-xs font-bold">
              Más acciones <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </summary>
            <div className="absolute right-0 z-30 mt-2 min-w-52 rounded-2xl border border-border bg-white p-2 shadow-xl">
              <StaffAttendanceExemptionDialog
                departmentId={row.department_id}
                employeeId={row.employee_id}
                employeeName={row.employee_name}
                defaultDate={row.period_start}
              />
            </div>
          </details>
        </div>
      </header>

      <div className="p-4">
        <p className="mb-2 text-xs font-semibold text-(--muted)">Detalle semanal</p>
        <div className="overflow-x-auto pb-1" aria-label={`Semana de asistencia de ${row.employee_name}`}>
          <div className="grid min-w-[47rem] grid-cols-7 gap-2">
            {row.days.map((day) => (
              <DaySummaryBadge key={`${row.employee_id}-${day.date}`} day={day} employeeId={row.employee_id} employeeName={row.employee_name} departmentId={row.department_id} />
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}

function DaySummaryBadge({ day, employeeId, employeeName, departmentId }: { day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay; employeeId?: number; employeeName?: string; departmentId?: number }) {
  const styles = getDaySummaryClasses(day);
  const summaryValue = getDaySummaryValue(day);
  const absenceEventDetail = getAbsenceEventDetail(day);
  const dayScheduleSummary = getDayScheduleSummary(day);
  const exemptionReason = formatExemptionReason(day.exemption_reason);

  return (
    <div
      className={`min-h-28 rounded-2xl border px-3 py-2 transition-colors duration-200 ${styles.container}`}
      title={formatCompactDateWithWeekday(day.date)}
    >
      <p className={`text-[10px] font-semibold uppercase tracking-wide ${styles.label}`}>{formatWeekdayChipLabel(day.date)}</p>
      {day.is_official_holiday ? <p className="mt-0.5 text-[9px] font-bold uppercase tracking-wide text-violet-700">{day.holiday_work_authorized ? "Turno autorizado" : "Descanso oficial"}</p> : null}
      <p className={`mt-1 text-sm leading-tight ${styles.value}`}>{summaryValue}</p>
      {exemptionReason ? <p className="mt-1 text-[10px] font-semibold leading-tight text-sky-700">Motivo: {exemptionReason}</p> : null}
      {day.is_official_holiday && day.official_holiday_name ? <p className="mt-1 text-[10px] font-medium leading-tight text-violet-700">{day.official_holiday_name}</p> : null}
      {absenceEventDetail ? (
        <p className="mt-1 text-[10px] font-semibold leading-tight text-rose-700">{absenceEventDetail}</p>
      ) : null}
      {dayScheduleSummary ? (
        <p className="mt-1 text-[10px] leading-tight text-slate-600">{dayScheduleSummary}</p>
      ) : null}
      {day.is_official_holiday && !day.holiday_work_authorized && employeeId && employeeName && departmentId && day.official_holiday_name ? <StaffHolidayWorkButton departmentId={departmentId} employeeId={employeeId} employeeName={employeeName} holidayDate={day.date} holidayName={day.official_holiday_name} /> : null}
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
