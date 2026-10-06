import Link from "next/link";
import { PrintNowButton } from "@/components/auto-print-on-load";
import { fetchBackendJson, requireStaffUser } from "@/lib/server-session";
import styles from "./report.module.css";

type Day = {
  date: string; contracted_seconds: number; worked_seconds: number | null;
  total_events: number; justified: boolean; exemption_reason: string | null;
  official_holiday: string | null; incomplete: boolean;
  first_event: string | null; last_event: string | null;
  schedule: { start: string; end: string }[];
};
type Row = {
  employee_id: number; employee_name: string; contracted_seconds: number;
  worked_seconds: number; difference_seconds: number; justified_days: number;
  incomplete_days: number; unmeasured_days: number; days: Day[];
};
type Report = { start_date: string; end_date: string; department_name: string; campus: string | null; rows: Row[] };
type Params = { department_id?: string; start_date?: string; end_date?: string; filter?: string; q?: string; sort?: string };
const reasons: Record<string, string> = {
  incapacidad: "Incapacidad", comision_institucional: "Comisión institucional",
  permiso_staff: "Permiso de staff", fuerza_mayor: "Fuerza mayor", home_office: "Home office", otro: "Otro",
};
function duration(seconds: number) {
  const minutes = Math.round(Math.abs(seconds) / 60);
  return `${seconds < 0 ? "−" : ""}${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}
const dateLabel = (value: string) => new Date(`${value}T12:00:00Z`).toLocaleDateString("es-MX", { timeZone: "UTC", day: "2-digit", month: "short", year: "numeric" });
function validWeek(start: string, end: string) {
  if (![start, end].every(value => /^\d{4}-\d{2}-\d{2}$/.test(value))) return false;
  const a = new Date(`${start}T00:00:00Z`), b = new Date(`${end}T00:00:00Z`);
  return Number.isFinite(a.getTime()) && Number.isFinite(b.getTime()) &&
    a.toISOString().slice(0, 10) === start && b.toISOString().slice(0, 10) === end &&
    a.getUTCDay() === 1 && b.getTime() - a.getTime() === 6 * 86400000;
}

export default async function WeeklyHoursPage({ searchParams }: { searchParams: Promise<Params> }) {
  const user = await requireStaffUser();
  const params = await searchParams;
  const backParams = new URLSearchParams({ view: "period" });
  for (const key of ["department_id", "start_date", "end_date", "filter", "q", "sort"] as const) {
    if (params[key]) backParams.set(key, params[key]);
  }
  const back = `/staff?${backParams}`;
  const start = params.start_date ?? "", end = params.end_date ?? "";
  if (!validWeek(start, end) || !/^[1-9]\d*$/.test(params.department_id ?? "")) {
    return <main className={styles.report}><h1>Reporte de horas semanal</h1><p>Selecciona un departamento y una sola semana completa, de lunes a domingo.</p><Link href={back}>Volver a la consulta</Link></main>;
  }
  const query = new URLSearchParams({ department_id: params.department_id!, start_date: start, end_date: end });
  const report = await fetchBackendJson<Report>(`/staff/weekly-hours?${query}`);
  const contracted = report.rows.reduce((sum, row) => sum + row.contracted_seconds, 0);
  const worked = report.rows.reduce((sum, row) => sum + row.worked_seconds, 0);
  const unmeasured = report.rows.reduce((sum, row) => sum + row.unmeasured_days, 0);
  return <main className={styles.report}>
    <nav className={styles.actions} aria-label="Acciones del reporte"><Link className="ghost-button px-4 py-3" href={back}>Volver a la consulta</Link><PrintNowButton /></nav>
    <header className={styles.header}><p>ESCUELA MODELO · ASISTENCIA INSTITUCIONAL</p><h1>Reporte de horas semanal</h1><h2>{report.campus ? `${report.campus} · ` : ""}{report.department_name}</h2><p>{dateLabel(start)} — {dateLabel(end)}</p><small>Emitido por {user.full_name} · {new Date().toLocaleString("es-MX", { timeZone: "America/Mexico_City" })}</small></header>
    <section className={styles.metrics} aria-label="Resumen semanal">
      <div>Colaboradores<strong>{report.rows.length}</strong></div>
      <div>Horas contratadas<strong>{duration(contracted)}</strong></div>
      <div>Horas trabajadas estimadas<strong>{duration(worked)}</strong></div>
      <div>Diferencia registrada<strong>{duration(worked - contracted)}</strong></div>
    </section>
    <aside className={styles.note}>
      <strong>Lectura del reporte · horas:minutos</strong>
      <p>Contratadas: suma de los bloques del horario aplicable a cada fecha, incluidas sus excepciones. Los descansos oficiales sin turno autorizado aportan 0 horas.</p>
      <p>Trabajadas estimadas: tiempo entre primera y última checada distinta, descontando las pausas entre bloques del horario. No comprueba permanencia continua. Con cero o una checada no se calcula tiempo; “—” no significa una falta.</p>
      <p>Las exenciones, incluido home office, se indican sin convertirlas en horas biométricas. La diferencia es informativa: no determina descuentos ni horas extra. Incluye toda la plantilla, sin filtros de incidencias o búsqueda.</p>
      {unmeasured > 0 && <p><strong>Datos parciales:</strong> {unmeasured} días con horario carecen de marcas suficientes para calcular horas. Los totales solo suman tiempo calculable; pueden cambiar al cargar nuevos lotes.</p>}
    </aside>
    <h2>Resumen por colaborador</h2>
    <div className={styles.tableWrap}><table><thead><tr><th>Colaborador</th><th>Contratadas</th><th>Trabajadas estimadas</th><th>Diferencia</th><th>Días justificados</th><th>Días sin tiempo calculable*</th></tr></thead><tbody>
      {report.rows.map(row => <tr key={row.employee_id}><th scope="row">{row.employee_name}</th><td>{duration(row.contracted_seconds)}</td><td>{duration(row.worked_seconds)}</td><td>{duration(row.difference_seconds)}</td><td>{row.justified_days}</td><td>{row.unmeasured_days}</td></tr>)}
      {report.rows.length === 0 && <tr><td colSpan={6}>No hay colaboradores asignados a este departamento.</td></tr>}
    </tbody><tfoot><tr><th>Total</th><td>{duration(contracted)}</td><td>{duration(worked)}</td><td>{duration(worked - contracted)}</td><td>{report.rows.reduce((sum, row) => sum + row.justified_days, 0)}</td><td>{unmeasured}</td></tr></tfoot></table></div>
    <p className={styles.caption}>* Días con horas contratadas y sin tiempo calculable. Pueden estar justificados; no equivalen a faltas.</p>
    {report.rows.map(row => <section key={row.employee_id} className={styles.detail}>
      <h2>{row.employee_name}</h2>
      <div className={styles.tableWrap}><table><thead><tr><th>Día</th><th>Horario aplicable</th><th>Primera / última checada</th><th>Contratadas</th><th>Trabajadas estimadas</th><th>Observaciones</th></tr></thead><tbody>{row.days.map(day => <tr key={day.date}>
        <th scope="row">{new Date(`${day.date}T12:00:00Z`).toLocaleDateString("es-MX", { timeZone: "UTC", weekday: "short", day: "2-digit", month: "short" }).toUpperCase()}</th>
        <td>{day.official_holiday ? "Descanso oficial" : day.schedule.map(block => `${block.start.slice(0, 5)}–${block.end.slice(0, 5)}`).join(" / ") || "Sin horario"}</td>
        <td>{day.first_event?.slice(0, 5) ?? "—"} / {day.total_events > 1 ? day.last_event?.slice(0, 5) : "—"}</td>
        <td>{duration(day.contracted_seconds)}</td><td>{day.worked_seconds === null ? "—" : duration(day.worked_seconds)}</td>
        <td>{[day.justified ? `Justificado: ${reasons[day.exemption_reason ?? ""] ?? day.exemption_reason ?? "Exención"}` : null, day.official_holiday, day.incomplete ? "Checada incompleta · tiempo no calculable" : day.total_events === 0 ? "Sin eventos" : null].filter(Boolean).join(" · ") || `${day.total_events} checadas`}</td>
      </tr>)}</tbody></table></div>
    </section>)}
  </main>;
}
