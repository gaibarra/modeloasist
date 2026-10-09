import Link from "next/link";
import { redirect } from "next/navigation";
import { requireStaffUser, fetchBackendJson } from "@/lib/server-session";
import { DepartmentSummary, StaffDefaultWeek } from "@/lib/auth";
import { canViewCampusHours, CampusHoursReport, executiveCampuses, hoursLabel, isCompleteWeek } from "@/lib/campus-hours";
import { PeriodDateRangeFields } from "@/components/period-date-range-fields";
import { PrintNowButton } from "@/components/auto-print-on-load";
import styles from "../hours/report.module.css";

type Params = { campus?: string; department_id?: string; start_date?: string; end_date?: string };
const dateLabel = (value: string) => new Date(`${value}T12:00:00Z`).toLocaleDateString("es-MX", { timeZone: "UTC", day: "2-digit", month: "long", year: "numeric" });

export default async function CampusHoursPage({ searchParams }: { searchParams: Promise<Params> }) {
  const user = await requireStaffUser();
  if (!canViewCampusHours(user.email)) redirect("/staff");
  const params = await searchParams;
  let campus = params.campus;
  if (!campus && params.department_id) {
    const departments = await fetchBackendJson<DepartmentSummary[]>("/staff/departments");
    campus = departments.find(d => String(d.id) === params.department_id)?.campus ?? undefined;
  }
  // Direct entry defaults to the campus of the requested rectoral visit.
  campus ??= "Valladolid";
  let start = params.start_date ?? "", end = params.end_date ?? "";
  if (!start && !end) {
    const defaults = await fetchBackendJson<StaffDefaultWeek>("/staff/mobile/default-week");
    start = defaults.start_date; end = defaults.end_date;
  }
  const valid = executiveCampuses.some(item => item === campus) && isCompleteWeek(start, end);
  const query = new URLSearchParams({ campus, start_date: start, end_date: end });
  const report = valid ? await fetchBackendJson<CampusHoursReport>(`/staff/campus-hours?${query}`) : null;
  const back = new URLSearchParams({ view: "period", start_date: start, end_date: end });
  if (params.department_id) back.set("department_id", params.department_id);
  return <main className={styles.report}>
    <nav className={styles.actions}><Link href={`/staff?${back}`} className="ghost-button px-4 py-3">Volver a asistencia</Link>{report && <><a href={`/api/staff/campus-hours?${query}&export=true`} className="ghost-button px-4 py-3">Exportar CSV</a><PrintNowButton /></>}</nav>
    <header className={styles.header}>
      <p>ESCUELA MODELO · RECTORÍA</p><h1>Reporte ejecutivo de horas por campus</h1>
      <h2>Campus {campus}</h2>
      {valid && <p>Semana del {dateLabel(start)} al {dateLabel(end)}</p>}
      <small>Elaborado por {user.full_name} · {new Date().toLocaleString("es-MX", { timeZone: "America/Mexico_City" })}</small>
    </header>
    <form className={`${styles.actions} mt-5 flex-wrap items-end`}>
      <label className="text-sm font-medium">Campus<select className="field-input" name="campus" defaultValue={campus}>{executiveCampuses.map(item => <option key={item}>{item}</option>)}</select></label>
      <PeriodDateRangeFields key={`${start}-${end}`} startDate={start} endDate={end} />
      <button type="submit" className="primary-button min-h-12 px-5 py-3">Consultar</button>
    </form>
    {!valid && <p role="alert" className="my-4 rounded-xl bg-amber-50 p-4">Selecciona un campus válido y una sola semana completa, de lunes a domingo.</p>}
    {report && <>
      <p className="my-4"><strong>{report.totals.employees} colaboradores</strong> · Orden alfabético por nombre registrado · Horas:minutos</p>
      <div className={styles.tableWrap}><table>
        <thead><tr><th>N.º</th><th>Colaborador</th><th>Contrato laboral</th><th>Programadas</th><th>Trabajadas estimadas</th><th>Programadas − contrato</th><th>Trabajadas − programadas</th><th>Observaciones</th></tr></thead>
        <tbody>{report.rows.map((row, index) => <tr key={row.employee_id}>
          <td>{index + 1}</td><th scope="row">{row.employee_name}</th><td>{hoursLabel(row.labor_contract_seconds)}</td><td>{hoursLabel(row.scheduled_seconds)}</td><td>{hoursLabel(row.worked_seconds)}</td>
          <td>{row.scheduled_contract_difference_seconds === null ? "—" : hoursLabel(row.scheduled_contract_difference_seconds)}</td><td>{hoursLabel(row.worked_scheduled_difference_seconds)}</td><td>{row.observations}</td>
        </tr>)}{!report.rows.length && <tr><td colSpan={8}>No hay colaboradores asignados a este campus.</td></tr>}</tbody>
        <tfoot><tr><th colSpan={2}>Totales</th><td>{hoursLabel(report.totals.labor_contract_seconds)}</td><td>{hoursLabel(report.totals.scheduled_seconds)}</td><td>{hoursLabel(report.totals.worked_seconds)}</td><td colSpan={3}>Cada persona se contabiliza una sola vez en este campus.</td></tr></tfoot>
      </table></div>
      <aside className={`${styles.note} mt-5`}>
        <strong>Alcance y lectura</strong>
        <p>Incluye todos los colaboradores asignados a departamentos activos del campus, aun sin checadas. No se divide la lista por departamento ni se presenta detalle diario. Las horas son por persona; no representan una distribución de tiempo entre sedes.</p>
        <p>Contrato laboral: referencia semanal vigente durante toda la semana. Programadas: horario efectivo, incluidas excepciones y descansos oficiales. Trabajadas estimadas: primera a última checada, descontando pausas programadas; con marcas insuficientes y justificación de entrada y salida se acreditan las horas del horario efectivo del día.</p>
        <p>Las horas acreditadas se suman al total y se identifican en observaciones. Con checadas suficientes no se duplica el horario; las exenciones parciales no acreditan una jornada completa. Cero horas registradas o una diferencia negativa no equivalen automáticamente a faltas ni descuentos. Los lotes pendientes pueden cambiar los resultados.</p>
      </aside>
    </>}
  </main>;
}
