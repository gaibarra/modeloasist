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
    weeks?: string;
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
const formatWeekdayDate = (periodStart: string, weekdayIndex: number) => {
  const start = parseLocalDate(periodStart);
  if (!start) return null;
  const value = new Date(start);
  value.setDate(start.getDate() + weekdayIndex);
  return value.toLocaleDateString("es-MX", { day: "2-digit", month: "short" }).replace(".", "").toUpperCase();
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

const formatStatus = (value: StaffMobilePeriodDay["status"]) => {
  switch (value) {
    case "on_time":
      return { label: "A tiempo", className: "print-chip print-chip--success" };
    case "late":
      return { label: "Retardo", className: "print-chip print-chip--warning" };
    case "absence":
      return { label: "Falta", className: "print-chip print-chip--danger" };
    case "left_early":
      return { label: "Salida anticipada", className: "print-chip print-chip--warning" };
    case "no_schedule":
      return { label: "Sin horario", className: "print-chip print-chip--info" };
    default:
      return { label: "Sin eventos", className: "print-chip print-chip--muted" };
  }
};

function isAbsenceStatus(value: StaffMobilePeriodDay["status"] | StaffEmployeeYearWeekDay["status"]) {
  return value === "absence";
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

async function fetchEmployeeYearSummary(departmentId: number, employeeId: number, weeks: number) {
  return fetchBackendJson<StaffEmployeeYearSummary>(
    `/staff/mobile/employee-year?department_id=${departmentId}&employee_id=${employeeId}&weeks=${weeks}`,
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
  const selectedWeeks = [2, 3, 4, 6, 8, 12].includes(Number(params.weeks)) ? Number(params.weeks) : 4;
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
    ? await fetchEmployeeYearSummary(selectedDepartmentId, selectedEmployeeId, selectedWeeks)
    : null;
  const absenceDays = employeeYearSummary ? countAbsenceDays(employeeYearSummary) : 0;

  const generatedAt = formatTimestamp(new Date());
  const totalEvents = rows.reduce((sum, row) => sum + row.total_events, 0);
  const totalRegisteredDays = rows.reduce((sum, row) => sum + row.active_days, 0);
  const totalLateDays = rows.reduce((sum, row) => sum + countLateDays(row.days), 0);
  const totalAbsenceDays = rows.reduce((sum, row) => sum + countAbsenceStatuses(row.days), 0);

  return (
    <main className="print-report-shell min-h-screen bg-(--page-background) px-4 py-6 text-foreground sm:px-6">
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
            display: none !important;
          }
          .print-individual-offset {
            padding-top: 0;
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
          background: #eef3f8;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: #52525b;
        }
          .print-table td {
          font-size: 10px;
          color: #1e293b;
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
        .print-report-shell { background: linear-gradient(180deg, #f7faff 0%, #ffffff 320px); }
        .print-hero { border: 1px solid #d7e2ef; background: linear-gradient(125deg, #ffffff 0%, #f1f6fc 100%); }
        .print-hero-mark { width: 8px; align-self: stretch; border-radius: 999px; background: linear-gradient(180deg, #1c4e80, #5ea2d6); }
        .print-meta-card { border: 1px solid #cfdeed; background: rgba(255,255,255,.86); box-shadow: 0 8px 18px rgba(30,65,110,.06); }
        .print-metric { border: 1px solid #d6e1ed; background: #ffffff; box-shadow: 0 6px 15px rgba(30,65,110,.05); }
        .print-metric-value { color: #163d68; letter-spacing: -.03em; }
        .print-table thead { border-bottom: 2px solid #b9cce0; }
        .print-table tbody tr:nth-child(even) { background: #fbfdff; }
        .print-table td { padding: .55rem .45rem; }
        .print-day { display: grid; gap: .24rem; min-width: 0; }
        .print-day-time { color: #163d68; font-size: 11px; font-weight: 800; letter-spacing: -.01em; }
        .print-day-date { color: #527aa5; font-size: 9px; font-weight: 800; letter-spacing: .05em; }
        .print-day-schedule { color: #64748b; font-size: 9px; line-height: 1.25; }
        .print-day-meta { color: #64748b; font-size: 9px; }
        .print-day-status { display: inline-flex; width: fit-content; border-radius: 999px; padding: .16rem .42rem; font-size: 9px; font-weight: 800; }
        .print-day-status--ok { background: #dcfce7; color: #166534; }
        .print-day-status--incident { background: #fee2e2; color: #b91c1c; }
        .print-day-status--warning { background: #fef3c7; color: #92400e; }
        .print-day-status--neutral { background: #eaf0f6; color: #52677e; }
        @media print {
          * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .print-report-shell { background: #ffffff; }
          .print-hero, .print-metric, .print-meta-card { box-shadow: none; }
          .print-table thead { display: table-header-group; }
          .print-table td { padding: .38rem .3rem; }
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

        <header className="print-card print-hero flex gap-4 rounded-[28px] p-5 shadow-sm sm:p-6">
          <div className="print-hero-mark hidden sm:block" aria-hidden="true" />
          <div className="flex min-w-0 flex-1 flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="section-eyebrow">
                {view === "individual" ? "Consulta individual" : "Consulta por periodo"}
              </p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-(--color-brand-strong)">Reporte de asistencia staff</h1>
              <p className="mt-2 text-sm text-(--muted)">
                Generado por {user.full_name} el {generatedAt}.
              </p>
            </div>
            <div className="print-meta-card grid shrink-0 gap-2 rounded-2xl px-4 py-3 text-sm text-foreground">
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
                <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
                  <div><p className="section-eyebrow">Detalle operativo</p><h2 className="mt-1 text-lg font-semibold text-(--color-brand-strong)">Reporte ejecutivo por periodo</h2></div>
                  <p className="text-xs text-(--muted)">Horario · eventos · estatus</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="print-table">
                    <thead>
                      <tr>
                        <th className="w-36">Semana</th>
                        <th className="w-56">Nombre / Departamento</th>
                        {WEEKDAY_COLUMNS.map((weekday) => (
                          <th key={weekday.index}><span className="block">{weekday.label}</span><span className="mt-0.5 block text-[9px] font-medium normal-case tracking-normal text-slate-500">{formatWeekdayDate(startDate, weekday.index)}</span></th>
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
                                <ExecutiveDayCell day={dayMap.get(weekday.index) ?? null} dateLabel={formatWeekdayDate(row.period_start, weekday.index)} />
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
                                  <ExecutiveDayCell day={dayMap.get(weekday.index) ?? null} dateLabel={formatWeekdayDate(week.week_start, weekday.index)} />
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
    <article className="print-subcard print-metric rounded-2xl p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-(--muted)">{label}</p>
      <p className="print-metric-value mt-2 text-lg font-semibold">{value}</p>
    </article>
  );
}

function ExecutiveDayCell({ day, dateLabel }: { day: StaffMobilePeriodDay | StaffEmployeeYearWeekDay | null; dateLabel?: string | null }) {
  if (!day) {
    return <div className="print-day"><p className="print-day-date">{dateLabel ?? "—"}</p><p className="text-center text-(--muted)">—</p></div>;
  }

  const status = formatStatus(day.status);
  const isAbsence = isAbsenceStatus(day.status);
  const absenceEventDetail = getAbsenceEventDetail(day);
  return (
    <div className="print-day">
      <p className="print-day-date">{dateLabel ?? day.date}</p>
      <p className="print-day-time">{formatTime(day.entry_event)} / {formatTime(day.exit_event)}</p>
      <p className="print-day-schedule">Hor. {formatScheduleIntervals(day.schedule_intervals, day.scheduled_start, day.scheduled_end)}</p>
      <p className="print-day-meta">{day.total_events} eventos</p>
      <p className={`print-day-status ${isAbsence ? "print-day-status--incident" : day.status === "late" || day.status === "left_early" ? "print-day-status--warning" : day.status === "on_time" ? "print-day-status--ok" : "print-day-status--neutral"}`}>{status.label}</p>
      {absenceEventDetail ? <p className="print-incident text-[9px]">{absenceEventDetail}</p> : null}
      {day.has_mixed_schedule ? <p className="print-day-meta">Horario mixto</p> : null}
    </div>
  );
}
