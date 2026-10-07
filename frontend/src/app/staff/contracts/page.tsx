import Link from "next/link";
import { fetchBackendJson, requireStaffUser } from "@/lib/server-session";
import { DepartmentSummary } from "@/lib/auth";
import { ContractReport, contractDuration } from "@/lib/labor-contracts";
import { PrintNowButton } from "@/components/auto-print-on-load";
import styles from "../hours/report.module.css";

type Params = { department_id?: string; campus?: string; contract_status?: string };
const states = { matches: "Coincide", lower: "Horario inferior", higher: "Horario superior", no_schedule: "Sin horario", pending_contract: "Contrato pendiente", pending_identity: "Identidad pendiente", not_in_file: "Sin información en este archivo" };
export default async function ContractsPage({ searchParams }: { searchParams: Promise<Params> }) {
  await requireStaffUser();
  const params = await searchParams;
  const departments = await fetchBackendJson<DepartmentSummary[]>("/staff/departments");
  const query = new URLSearchParams();
  if (params.department_id && departments.some(d => String(d.id) === params.department_id)) query.set("department_id", params.department_id);
  if (params.campus) query.set("campus", params.campus);
  if (params.contract_status && params.contract_status in states) query.set("contract_status", params.contract_status);
  const result = await fetchBackendJson<ContractReport>(`/staff/labor-contracts?${query}`);
  return <main className={styles.report}>
    <nav className={styles.actions}><Link href="/staff" className="ghost-button p-3">Volver a asistencia</Link><a className="ghost-button p-3" href={`/api/staff/labor-contracts?${query}&export=true`}>Exportar CSV</a><PrintNowButton /></nav>
    <header className={styles.header}><h1>Contratos y horarios pendientes</h1><p>Agosto–diciembre 2026 · Contrato laboral frente al horario semestral guardado</p></header>
    <form className={`${styles.actions} mt-4 flex-wrap`}>
      <label>Campus<select name="campus" defaultValue={params.campus ?? ""} className="field-input"><option value="">Todos mis campus</option>{[...new Set(departments.map(d => d.campus).filter(Boolean))].map(c => <option key={c!} value={c!}>{c}</option>)}</select></label>
      <label>Departamento<select name="department_id" defaultValue={query.get("department_id") ?? ""} className="field-input"><option value="">Todos mis departamentos</option>{departments.map(d => <option key={d.id} value={d.id}>{d.campus} · {d.name}</option>)}</select></label>
      <label>Estado<select name="contract_status" defaultValue={query.get("contract_status") ?? ""} className="field-input"><option value="">Todos los estados</option>{Object.entries(states).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <button className="primary-button p-3" type="submit">Consultar</button>
    </form>
    {!result.available && <p role="status">La consulta de contratos estará disponible después de aplicar la migración correspondiente.</p>}
    <p className="my-4">{new Set(result.rows.map(r => r.employee_id)).size} colaboradores · {result.rows.length} asignaciones. Las personas con varios departamentos aparecen en cada asignación; sus horas son por persona, no se suman entre departamentos.</p>
    <p className="mb-4">Formato horas:minutos. Las diferencias no alteran automáticamente horarios ni contratos. No se consideran excepciones, festivos o exenciones para esta comparación.</p>
    <div className={styles.tableWrap}><table><thead><tr><th>Colaborador</th><th>Campus / departamento</th><th>Contrato</th><th>Horario semestral</th><th>Diferencia</th><th>Estado / archivo</th></tr></thead><tbody>
      {result.rows.map(row => <tr key={`${row.employee_id}-${row.department_id}`}><th scope="row">{row.employee_name}</th><td>{row.campus} · {row.department_name}</td><td>{contractDuration(row.contract_minutes)}</td><td>{contractDuration(row.scheduled_minutes)}</td><td>{contractDuration(row.difference_minutes)}</td><td>{row.status_label}<br /><small>{row.source_presence}</small></td></tr>)}
      {!result.rows.length && <tr><td colSpan={6}>No hay colaboradores con estos filtros.</td></tr>}
    </tbody></table></div>
  </main>;
}
