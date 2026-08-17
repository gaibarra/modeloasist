import Link from "next/link";

import { AutoPrintOnLoad, PrintNowButton } from "@/components/auto-print-on-load";
import {
  DepartmentSummary,
  StaffDefaultWeek,
  StaffDepartmentEmployeeSummary,
  StaffEmployeeYearWeekDay,
  StaffEmployeeYearSummary,
  StaffMobilePeriodDay,
  StaffMobilePeriodRow,
  StaffScheduleInterval,
} from "@/lib/auth";
import { fetchBackendJson, requireStaffUser } from "@/lib/server-session";

type StaffPrintPageProps = {
  searchParams?: Promise<{
    view?: string;
    department_id?: string;
    start_date?: string;
    end_date?: string;
    employee_id?: string;
  }>;
};

const formatTime = (value: string | null) => (value ? value.slice(0, 5) : "—");
const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;
const formatTimestamp = (value: Date) =>
  value.toLocaleString("es-MX", {
    dateStyle: "medium",
    timeStyle: "short",
  });
const WEEKDAY_COLUMNS = [
  { index: 0, label: "Lun" },
  { index: 1, label: "Mar" },
  { index: 2, label: "Mié" },
  { index: 3, label: "Jue" },
  { index: 4, label: "Vie" },
  { index: 5, label: "Sáb" },
  { index: 6, label: "Dom" },
];
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

const formatStatus = (value: StaffMobilePeriodDay["status"]) => {
  switch (value) {
    case "on_time":
      return { label: "A tiempo", className: "print-chip print-chip--success" };
    case "late":
      return { label: "Retardo", className: "print-chip print-chip--danger" };
    case "absence":
      return { label: "Falta", className: "print-chip print-chip--danger" };
    case "left_early":
      return { label: "Salida anticipada", className: "print-chip print-chip--danger" };
    case "no_schedule":
      return { label: "Sin horario", className: "print-chip print-chip--info" };
    default:
      return { label: "Sin eventos", className: "print-chip print-chip--muted" };
  }
};

function isIncidentStatus(value: StaffMobilePeriodDay["status"] | StaffEmployeeYearWeekDay["status"]) {
  return value === "late" || value === "left_early" || value === "absence";
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

function getWeekdayIndex(value: string) {
  const parsed = parseLocalDate(value);
  if (!parsed) {
    return null;
  }
  return (parsed.getDay() + 6) % 7;
}

function buildWeekdayMap<T extends { date: string }>(days: T[]) {
  const map = new Map<number, T>();
  for (const day of days) {
    const weekdayIndex = getWeekdayIndex(day.date);
    if (weekdayIndex !== null) {
      map.set(weekdayIndex, day);
    }
  }
  return map;
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

async function fetchEmployeeYearSummary(departmentId: number, employeeId: number) {
  return fetchBackendJson<StaffEmployeeYearSummary>(
    `/staff/mobile/employee-year?department_id=${departmentId}&employee_id=${employeeId}`,
  );
}

export default async function StaffPrintPage({ searchParams }: StaffPrintPageProps) {
  const user = await requireStaffUser();
  const params = (await searchParams) ?? {};
  const view = params.view === "individual" ? "individual" : "period";
  const defaultRange = await fetchDefaultWeekRange();
  const departments = await fetchDepartments();
  const defaultDepartmentId = departments[0]?.id ?? null;
  const selectedDepartmentId = Number(params.department_id ?? defaultDepartmentId ?? 0) || 0;
  const selectedDepartment = departments.find((department) => department.id === selectedDepartmentId) ?? null;
  const selectedEmployeeId = Number(params.employee_id ?? 0) || 0;
  const startDate = params.start_date ?? defaultRange.startDate;
  const endDate = params.end_date ?? defaultRange.endDate;
  const validationError = validatePeriodRange(startDate, endDate);

  const rows = view === "period" && selectedDepartmentId > 0 && !validationError
    ? await fetchPeriodAttendance(selectedDepartmentId, startDate, endDate)
    : [];

  const departmentEmployees = view === "individual" && selectedDepartmentId > 0
    ? await fetchDepartmentEmployees(selectedDepartmentId)
    : [];
  const hasSelectedEmployee = departmentEmployees.some((employee) => employee.id === selectedEmployeeId);
  const employeeYearSummary = view === "individual" && selectedDepartmentId > 0 && hasSelectedEmployee
    ? await fetchEmployeeYearSummary(selectedDepartmentId, selectedEmployeeId)
    : null;
  const absenceDays = employeeYearSummary ? countAbsenceDays(employeeYearSummary) : 0;

  const generatedAt = formatTimestamp(new Date());
  const totalEvents = rows.reduce((sum, row) => sum + row.total_events, 0);
  const totalRegisteredDays = rows.reduce((sum, row) => sum + row.active_days, 0);
  const totalLateDays = rows.reduce((sum, row) => sum + countLateDays(row.days), 0);
  const totalAbsenceDays = rows.reduce((sum, row) => sum + countAbsenceStatuses(row.days), 0);

  return (
    <main className="min-h-screen bg-(--page-background) px-4 py-6 text-foreground sm:px-6">
      <AutoPrintOnLoad />
      <style>{`
        @media print {
          @page {
            size: landscape;
            margin: 10mm;
          }
          html, body {
            background: #ffffff;
          }
          .print-hidden {
            display: none !important;
          }
          .print-card, .print-subcard, .print-table-row {
            break-inside: avoid;
            page-break-inside: avoid;
          }
          .print-flow-card {
            break-inside: auto !important;
            page-break-inside: auto !important;
          }
          .print-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            display: flex;
            justify-content: flex-end;
            font-size: 10px;
            color: #52525b;
          }
          .print-footer::after {
            content: "Página " counter(page) " de " counter(pages);
          }
          .print-individual-running-header {
            display: flex !important;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            padding: 0 0 6mm 0;
            border-bottom: 1px solid #d4d4d8;
            background: #ffffff;
          }
          .print-individual-offset {
            padding-top: 24mm;
          }
        }
        .print-table {
          width: 100%;
          border-collapse: collapse;
          table-layout: fixed;
        }
        .print-table th,
        .print-table td {
          border: 1px solid #d4d4d8;
          padding: 0.55rem;
          vertical-align: top;
        }
        .print-table th {
          background: #f4f4f5;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: #52525b;
        }
        .print-table td {
          font-size: 11px;
          color: #18181b;
        }
        .print-chip {
          display: inline-flex;
          align-items: center;
          border-radius: 9999px;
          padding: 0.3rem 0.65rem;
          font-size: 11px;
          font-weight: 700;
        }
        .print-chip--success { background: #dcfce7; color: #166534; }
        .print-chip--warning { background: #fef3c7; color: #92400e; }
        .print-chip--danger { background: #fee2e2; color: #b91c1c; }
        .print-chip--info { background: #e0f2fe; color: #075985; }
        .print-chip--muted { background: #f1f5f9; color: #475569; }
        .print-incident {
          color: #b91c1c;
          font-weight: 700;
        }
        .print-single-line {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .print-individual-running-header {
          display: none;
        }
      `}</style>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        {view === "individual" && employeeYearSummary ? (
          <div className="print-individual-running-header" aria-hidden="true">
            <div>
              <p className="section-eyebrow">Colaborador</p>
              <p className="text-base font-semibold text-(--color-brand-strong)">{employeeYearSummary.employee_name}</p>
              <p className="text-xs text-(--muted)">Departamento: {employeeYearSummary.department_name}</p>
              <p className="text-xs text-(--muted)">Campus: {employeeYearSummary.campus ?? "Sin campus"}</p>
            </div>
            <div className="text-right text-xs text-(--muted)">
              <p className="font-semibold">Periodo</p>
              <p>{employeeYearSummary.window_start} → {employeeYearSummary.window_end}</p>
            </div>
          </div>
        ) : null}
        <div className="print-hidden brand-panel flex items-center justify-between gap-3 px-4 py-3">
          <div>
            <p className="section-eyebrow">Vista imprimible</p>
            <p className="text-sm text-(--muted)">Se abrirá el diálogo de impresión automáticamente.</p>
          </div>
          <div className="flex items-center gap-2">
            <PrintNowButton />
            <Link href="/staff" className="secondary-button px-4 py-2 text-sm">
              Volver
            </Link>
          </div>
        </div>

        <header className="print-card brand-panel p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="section-eyebrow">
                {view === "individual" ? "Consulta individual" : "Consulta por periodo"}
              </p>
              <h1 className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">Reporte de asistencia staff</h1>
              <p className="mt-2 text-sm text-(--muted)">
                Generado por {user.full_name} el {generatedAt}.
              </p>
            </div>
            <div className="surface-muted grid gap-2 px-4 py-3 text-sm text-foreground">
              <p><span className="font-semibold">Departamento:</span> {selectedDepartment?.name ?? "Sin selección"}</p>
              <p><span className="font-semibold">Campus:</span> {selectedDepartment?.campus ?? "Sin campus"}</p>
              {view === "period" ? (
                <p><span className="font-semibold">Periodo:</span> {startDate} → {endDate}</p>
              ) : (
                <p><span className="font-semibold">Ventana:</span> {employeeYearSummary?.window_start ?? "2026-01-01"} → {employeeYearSummary?.window_end ?? defaultRange.endDate}</p>
              )}
            </div>
          </div>
        </header>

        {view === "period" ? (
          <section className="space-y-4">
            {validationError ? (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{validationError}</div>
            ) : null}
            {!validationError ? (
              <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
                <PrintMetricCard label="Colaboradores" value={String(rows.length)} />
                <PrintMetricCard label="Días registrados" value={String(totalRegisteredDays)} />
                <PrintMetricCard label="Retardos" value={String(totalLateDays)} />
                <PrintMetricCard label="Faltas" value={String(totalAbsenceDays)} />
                <PrintMetricCard label="Eventos acumulados" value={String(totalEvents)} />
                <PrintMetricCard label="Periodo" value={`${startDate} → ${endDate}`} />
              </div>
            ) : null}
            {rows.length === 0 ? (
              <div className="surface-card p-6 text-sm text-(--muted)">
                {validationError ? "Corrige el rango antes de imprimir." : "No hay resultados para imprimir en el periodo seleccionado."}
              </div>
            ) : (
              <article className="print-flow-card overflow-hidden rounded-3xl border border-border bg-white shadow-sm">
                <div className="border-b border-border px-5 py-4">
                  <h2 className="text-lg font-semibold text-(--color-brand-strong)">Reporte ejecutivo por periodo</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="print-table">
                    <thead>
                      <tr>
                        <th className="w-36">Semana</th>
                        <th className="w-56">Nombre / Departamento</th>
                        {WEEKDAY_COLUMNS.map((weekday) => (
                          <th key={weekday.index}>{weekday.label}</th>
                        ))}
                        <th className="w-24">Eventos</th>
                        <th className="w-24">Días</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => {
                        const dayMap = buildWeekdayMap(row.days);
                        return (
                          <tr key={`${row.employee_id}-${row.period_start}-${row.period_end}`} className="print-table-row">
                            <td>
                              <p className="font-semibold">{row.period_start}</p>
                              <p className="text-(--muted)">{row.period_end}</p>
                            </td>
                            <td>
                              <p className="print-single-line font-semibold text-(--color-brand-strong)">{row.employee_name} · {row.department_name}</p>
                              <p className="text-(--muted)"><span className="font-semibold">Campus:</span> {row.campus ?? "Sin campus"}</p>
                            </td>
                            {WEEKDAY_COLUMNS.map((weekday) => (
                              <td key={`${row.employee_id}-${weekday.index}`}>
                                <ExecutiveDayCell day={dayMap.get(weekday.index) ?? null} />
                              </td>
                            ))}
                            <td className="text-center font-semibold">{row.total_events}</td>
                            <td className="text-center font-semibold">{row.active_days}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </article>
            )}
          </section>
        ) : (
          <section className="space-y-4 print-individual-offset">
            {employeeYearSummary ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <PrintMetricCard label="Días registrados" value={String(employeeYearSummary.total_days)} />
                  <PrintMetricCard label="Retardos" value={String(employeeYearSummary.late_days)} />
                  <PrintMetricCard label="Faltas" value={String(absenceDays)} />
                  <PrintMetricCard label="Puntualidad" value={formatPercent(employeeYearSummary.punctuality_rate)} />
                  <PrintMetricCard label="Horario registrado" value={formatScheduleIntervals(employeeYearSummary.registered_schedule_intervals)} />
                </div>

                <article className="print-card rounded-3xl border border-border bg-white p-5 shadow-sm">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="section-eyebrow">Colaborador</p>
                      <h2 className="text-lg font-semibold text-(--color-brand-strong)">{employeeYearSummary.employee_name}</h2>
                      <p className="text-sm text-(--muted)">{employeeYearSummary.employee_email ?? "Sin correo registrado"}</p>
                      <p className="mt-1 text-sm text-(--muted)">
                        <span className="font-semibold">Departamento:</span> {employeeYearSummary.department_name}
                      </p>
                      <p className="text-sm text-(--muted)">
                        <span className="font-semibold">Campus:</span> {employeeYearSummary.campus ?? "Sin campus"}
                      </p>
                    </div>
                    <div className="surface-muted px-4 py-3 text-sm text-foreground">
                      <p><span className="font-semibold">Periodo:</span> {employeeYearSummary.window_start} → {employeeYearSummary.window_end}</p>
                      <p><span className="font-semibold">Año:</span> {employeeYearSummary.report_year}</p>
                    </div>
                  </div>
                </article>

                {employeeYearSummary.weeks.length === 0 ? (
                  <div className="surface-card p-6 text-sm text-(--muted)">
                    No hay semanas para imprimir en la consulta individual.
                  </div>
                ) : (
                  <article className="print-flow-card overflow-hidden rounded-3xl border border-border bg-white shadow-sm">
                    <div className="border-b border-border px-5 py-4">
                      <h3 className="text-lg font-semibold text-(--color-brand-strong)">Reporte ejecutivo individual</h3>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="print-table">
                        <thead>
                          <tr>
                            <th className="w-36">Semana</th>
                            {WEEKDAY_COLUMNS.map((weekday) => (
                              <th key={weekday.index}>{weekday.label}</th>
                            ))}
                            <th className="w-24">Eventos</th>
                            <th className="w-24">Días</th>
                          </tr>
                        </thead>
                        <tbody>
                          {employeeYearSummary.weeks.map((week) => {
                            const dayMap = buildWeekdayMap(week.days);
                            return (
                              <tr key={`${week.week_start}-${week.week_end}`} className="print-table-row">
                                <td>
                                  <p className="font-semibold">{week.week_start}</p>
                                  <p className="text-(--muted)">{week.week_end}</p>
                                </td>
                                {WEEKDAY_COLUMNS.map((weekday) => (
                                  <td key={`${week.week_start}-${weekday.index}`}>
                                    <ExecutiveDayCell day={dayMap.get(weekday.index) ?? null} />
                                  </td>
                                ))}
                                <td className="text-center font-semibold">{week.total_events}</td>
                                <td className="text-center font-semibold">{week.active_days}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </article>
                )}
              </>
            ) : (
              <div className="surface-card p-6 text-sm text-(--muted)">
                {selectedEmployeeId > 0
                  ? "No hay una consulta individual válida para imprimir con los parámetros actuales."
                  : "Selecciona un colaborador antes de imprimir la consulta individual."}
              </div>
            )}
          </section>
        )}
        <div className="print-footer" aria-hidden="true" />
      </div>
    </main>
  );
}

function PrintMetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="print-subcard surface-muted p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-(--muted)">{label}</p>
      <p className="mt-2 text-lg font-semibold text-(--color-brand-strong)">{value}</p>
    </article>
  );
}

function ExecutiveDayCell({ day }: { day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay | null }) {
  if (!day) {
    return <p className="text-center text-(--muted)">—</p>;
  }

  const status = formatStatus(day.status);
  const hasIncident = isIncidentStatus(day.status);
  const absenceEventDetail = getAbsenceEventDetail(day);
  return (
    <div className="space-y-1">
      <p className="font-semibold">{formatTime(day.entry_event)} / {formatTime(day.exit_event)}</p>
      <p className="text-(--muted)">{formatScheduleIntervals(day.schedule_intervals, day.scheduled_start, day.scheduled_end)}</p>
      <p className="text-(--muted)">Ev: {day.total_events}</p>
      <p className={hasIncident ? "print-incident" : "font-medium"}>{status.label}</p>
      {absenceEventDetail ? <p className="print-incident">{absenceEventDetail}</p> : null}
      {day.entry_event_inferred || day.exit_event_inferred ? (
        <p className="print-incident">Inferida</p>
      ) : null}
      {day.has_mixed_schedule ? <p className="print-incident">Mixto</p> : null}
    </div>
  );
}
