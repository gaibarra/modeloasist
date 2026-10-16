"use client";
import { useEffect, useState } from "react";
type Contract = { id: number; weekly_minutes: number | null; job_title: string; department_code: string; department_name: string; active: boolean };
type Data = { available: boolean; eligible: boolean; current: Contract | null; legacy_minutes: number | null; history: Contract[] };
export function CollaboratorContract({ employeeId }: { employeeId: number }) {
  const [data, setData] = useState<Data | null>(null);
  const [hours, setHours] = useState(""); const [job, setJob] = useState("");
  const [code, setCode] = useState(""); const [department, setDepartment] = useState("");
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  function populate(d: Data) {
    setData(d);setHours(d.current?.weekly_minutes == null ? "" : String(d.current.weekly_minutes / 60));
    setJob(d.current?.job_title ?? "");setCode(d.current?.department_code ?? "");setDepartment(d.current?.department_name ?? "");
  }
  useEffect(() => {
    const controller = new AbortController(); setData(null);setError("");setNotice("");
    fetch(`/api/colaboradores/${employeeId}/contract`, { cache: "no-store", signal: controller.signal }).then(async r => {
      const d = await r.json(); if (!r.ok) throw new Error(d.detail ?? "No se pudo cargar el contrato");
      if (!controller.signal.aborted) populate(d);
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [employeeId, refresh]);
  async function save() {
    setBusy(true);setError("");setNotice("");
    try {
      const r = await fetch(`/api/colaboradores/${employeeId}/contract`, { method: "PUT", headers: { "content-type": "application/json" },
        body: JSON.stringify({ expected_id: data?.current?.id ?? null, weekly_hours: hours === "" ? null : hours,
          job_title: job, department_code: code, department_name: department }) });
      const d = await r.json();if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Revisa las horas y los campos del contrato");
      populate(d);setNotice("Contrato CME guardado. Los reportes de agosto–diciembre de 2026 usarán esta referencia.");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <fieldset className="space-y-3 rounded-xl border p-4">
    <legend className="font-semibold">Contrato laboral · CME / Mérida</legend>
    <p className="text-sm">Vigencia: 1 agosto – 31 diciembre 2026. Se guarda por separado del perfil y conserva historial.</p>
    {error && <p role="alert">{error} <button type="button" disabled={busy} onClick={() => setRefresh(v => v + 1)}>Recargar contrato</button></p>}
    {!data && !error && <p role="status">Cargando contrato…</p>}
    {data && (!data.available ? <p>La migración de contratos por campus está pendiente.</p> : !data.eligible ? <p>Esta edición está disponible solo para colaboradores asignados a CME. No se modifica su contrato de otra sede.</p> : <>
      {data.legacy_minutes !== null && <p className="text-sm">Referencia anterior sin desglose de campus: {data.legacy_minutes / 60} h. Se conserva para otras sedes.</p>}
      <label className="block">Horas semanales de contrato<input className="field-input" type="number" min="0" max="168" step="any" value={hours} disabled={busy} onChange={e => setHours(e.target.value)} /><small>Vacío = Contrato pendiente. No equivale a cero horas.</small></label>
      <label className="block">Puesto<input className="field-input" maxLength={200} value={job} disabled={busy} onChange={e => setJob(e.target.value)} /></label>
      <label className="block">Clave del departamento laboral<input className="field-input" maxLength={100} value={code} disabled={busy} onChange={e => setCode(e.target.value)} /></label>
      <label className="block">Departamento laboral<input className="field-input" maxLength={200} value={department} disabled={busy} onChange={e => setDepartment(e.target.value)} /><small>Informativo: no modifica asignaciones, campus ni permisos.</small></label>
      <p className="text-sm">Guardar afectará la referencia contractual de CME en los reportes históricos de esta vigencia, no los horarios ni las checadas.</p>
      <button type="button" className="primary-button px-4 py-3" disabled={busy} onClick={save}>{busy ? "Guardando…" : "Guardar contrato CME"}</button>
      {data.history.length > 0 && <details><summary>Historial del contrato ({data.history.length})</summary><ul>{data.history.map(c => <li key={c.id}>Versión {c.id} · {c.active ? "Vigente" : "Reemplazada"} · {c.weekly_minutes === null ? "Contrato pendiente" : `${c.weekly_minutes / 60} h`} · {c.job_title} · {c.department_name}</li>)}</ul></details>}
    </>)}
    {notice && <p role="status">{notice}</p>}
  </fieldset>;
}
