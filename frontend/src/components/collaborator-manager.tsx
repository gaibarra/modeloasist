"use client";
import { useEffect, useRef, useState } from "react";
import { Building2, ChevronLeft, ChevronRight, Pencil, Plus, Search, ShieldCheck, Trash2, Users, X, Loader2 } from "lucide-react";
import styles from "./collaborator-manager.module.css";
type Employee = { id: number; nombre: string; email: string; campus: string | null; departamento: string; division: string | null; external_employee_id: number | null; department_ids: number[]; primary_department_id: number | null };
type Department = { id: number; name: string; campus: string | null; active: boolean };
type Result = { items: Employee[]; total: number; registered: number };
const empty = { nombre: "", email: "", department_ids: [] as number[], primary_department_id: null as number | null, external_employee_id: null as number | null, division: "" };
async function api(path: string, init?: RequestInit) {
  const r = await fetch(`/api/colaboradores${path}`, init);
  const data = r.status === 204 ? null : await r.json();
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Revisa los datos del formulario.");
  return data;
}
export function CollaboratorManager() {
  const [result, setResult] = useState<Result>({ items: [], total: 0, registered: 0 });
  const [departments, setDepartments] = useState<Department[]>([]);
  const [q, setQ] = useState(""); const [department, setDepartment] = useState(""); const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<Employee | null>(null); const [mode, setMode] = useState<"create" | "edit" | "detail" | "delete" | null>(null);
  const [form, setForm] = useState(empty); const [saving, setSaving] = useState(false); const [formError, setFormError] = useState(""); const [confirmation, setConfirmation] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { let active = true; api("/departments").then(d => { if (active) setDepartments(d); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true); setError("");
      try {
        const data = await api(`?${new URLSearchParams({ q, offset: String(page * 20), ...(department ? { department_id: department } : {}) })}`, { signal: controller.signal });
        if (!controller.signal.aborted) { setResult(data); if (page > 0 && !data.items.length) setPage(0); }
      } catch (e) { if (!controller.signal.aborted) setError((e as Error).message); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [q, department, page, revision]);
  function open(next: typeof mode, e: Employee | null = null) {
    setSelected(e); setForm(e ? { nombre: e.nombre, email: e.email, department_ids: e.department_ids, primary_department_id: e.primary_department_id, external_employee_id: e.external_employee_id, division: e.division ?? "" } : empty);
    setFormError(""); setConfirmation(""); setMode(next); dialog.current?.showModal();
  }
  function close() { if (!saving) { dialog.current?.close(); setMode(null); } }
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setFormError("");
    try {
      if (mode === "delete") await api(`/${selected!.id}`, { method: "DELETE" });
      else await api(mode === "create" ? "" : `/${selected!.id}`, { method: mode === "create" ? "POST" : "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(form) });
      setNotice(mode === "delete" ? "Colaborador eliminado." : mode === "create" ? "Colaborador registrado correctamente." : "Cambios guardados.");
      dialog.current?.close(); setMode(null); setRevision(r => r + 1);
    } catch (e) { setFormError((e as Error).message); } finally { setSaving(false); }
  }
  return <section className={styles.manager}>
    <div className={styles.stats}><div><Users /><span>Colaboradores registrados<strong>{result.registered.toLocaleString("es-MX")}</strong></span></div><div><Building2 /><span>Departamentos<strong>{departments.length}</strong></span></div><div><ShieldCheck /><span>Acceso exclusivo<strong className={styles.owner}>gaibarra@hotmail.com</strong></span></div></div>
    <div className={styles.directory}><div className={styles.heading}><div><h2>Directorio de colaboradores</h2><p>Consulta perfiles, actualiza datos y administra asignaciones.</p></div><button className="primary-button" onClick={() => open("create")}><Plus size={18} /> Nuevo colaborador</button></div>
      <div className={styles.filters}><label className={styles.search}><Search size={18} /><input aria-label="Buscar por nombre o correo" placeholder="Buscar por nombre o correo…" value={q} onChange={e => { setQ(e.target.value); setPage(0); }} /></label><select aria-label="Filtrar departamento" value={department} onChange={e => { setDepartment(e.target.value); setPage(0); }}><option value="">Todos los departamentos</option>{departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
      {notice && <p role="status" className={styles.success}>{notice}</p>}{error && <p role="alert" className={styles.error}>{error} <button onClick={() => setRevision(r => r + 1)}>Reintentar</button></p>}
      <div className={styles.tableWrap} aria-busy={loading}><table><thead><tr><th>Colaborador</th><th>Departamento principal</th><th>Campus</th><th><span className={styles.sr}>Acciones</span></th></tr></thead><tbody>{!error && result.items.map(e => <tr key={e.id}><td><button className={styles.profile} onClick={() => open("detail", e)}><span className={styles.avatar}>{e.nombre.split(/\s+/).slice(0, 2).map(n => n[0]).join("")}</span><span><strong>{e.nombre}</strong><small>{e.email}</small></span></button></td><td>{e.departamento}<small>{e.department_ids.length > 1 ? `${e.department_ids.length} asignaciones` : ""}</small></td><td><span className={styles.badge}>{e.campus || "Sin campus"}</span></td><td><div className={styles.actions}><button aria-label={`Editar ${e.nombre}`} title="Editar" onClick={() => open("edit", e)}><Pencil size={17} /></button><button aria-label={`Eliminar ${e.nombre}`} title="Eliminar" onClick={() => open("delete", e)}><Trash2 size={17} /></button></div></td></tr>)}</tbody></table>{loading && <p className={styles.empty}><Loader2 size={18} className="animate-spin" /> Cargando directorio…</p>}{!loading && !error && !result.items.length && <div className={styles.empty}><Users size={30} /><strong>No encontramos colaboradores</strong><p>Prueba otro nombre o cambia el departamento.</p></div>}</div>
      <footer className={styles.footer}><span>{result.total ? `${page * 20 + 1}–${Math.min((page + 1) * 20, result.total)} de ${result.total}` : "0 resultados"}</span><div><button aria-label="Página anterior" disabled={!page || loading} onClick={() => setPage(p => p - 1)}><ChevronLeft size={18} /></button><span>Página {page + 1}</span><button aria-label="Página siguiente" disabled={(page + 1) * 20 >= result.total || loading} onClick={() => setPage(p => p + 1)}><ChevronRight size={18} /></button></div></footer>
    </div>
    <dialog ref={dialog} className={styles.dialog} onCancel={e => { if (saving) e.preventDefault(); else setMode(null); }}><div className={styles.dialogHead}><div><p>ESCUELA MODELO · DIRECTORIO</p><h2>{mode === "create" ? "Nuevo colaborador" : mode === "edit" ? "Editar colaborador" : mode === "delete" ? "Eliminar colaborador" : "Ficha del colaborador"}</h2></div><button aria-label="Cerrar" onClick={close} disabled={saving}><X /></button></div>
      {mode === "detail" && selected ? <div className={styles.detail}><span className={styles.avatar}>{selected.nombre[0]}</span><h3>{selected.nombre}</h3><p>{selected.email}</p><dl>{[["Campus", selected.campus], ["División", selected.division], ["Identificador de checador", selected.external_employee_id], ["ID de registro", selected.id]].map(([label, value]) => <div key={String(label)}><dt>{label}</dt><dd>{value || "Sin registro"}</dd></div>)}</dl><h4>Departamentos asignados</h4>{departments.filter(d => selected.department_ids.includes(d.id)).map(d => <p key={d.id}>{d.name}{d.id === selected.primary_department_id ? " · Principal" : ""}</p>)}<button className="primary-button" onClick={() => open("edit", selected)}><Pencil size={17} /> Editar datos</button></div> : <form onSubmit={submit} className={styles.form}>
        {mode === "delete" ? <><p>Eliminarás el registro de <strong>{selected?.nombre}</strong>. Esta acción es permanente. Los colaboradores con historial asociado están protegidos.</p><label>Escribe ELIMINAR para confirmar<input autoFocus value={confirmation} onChange={e => setConfirmation(e.target.value)} required pattern="ELIMINAR" /></label></> : <>
          <label>Nombre completo<input autoFocus required minLength={2} maxLength={200} value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} /></label><label>Correo electrónico<input type="email" required maxLength={254} value={form.email} readOnly={selected?.email.toLowerCase() === "gaibarra@hotmail.com"} onChange={e => setForm({ ...form, email: e.target.value })} /></label>
          <div className={styles.two}><label>Identificador de checador<input type="number" min={1} max={Number.MAX_SAFE_INTEGER} value={form.external_employee_id ?? ""} onChange={e => setForm({ ...form, external_employee_id: e.target.value ? Number(e.target.value) : null })} /></label><label>División<input maxLength={128} value={form.division} onChange={e => setForm({ ...form, division: e.target.value })} /></label></div>
          <fieldset><legend>Departamentos asignados <small>Selecciona uno o más</small></legend><div className={styles.departmentList}>{departments.filter(d => d.active || form.department_ids.includes(d.id)).map(d => <label key={d.id}><input type="checkbox" checked={form.department_ids.includes(d.id)} onChange={e => { const ids = e.target.checked ? [...form.department_ids, d.id] : form.department_ids.filter(id => id !== d.id); setForm({ ...form, department_ids: ids, primary_department_id: ids.includes(form.primary_department_id ?? 0) ? form.primary_department_id : ids[0] ?? null }); }} /><span>{d.name}<small>{d.campus || "Sin campus"}{!d.active ? " · Inactivo" : ""}</small></span></label>)}</div></fieldset>
          <label>Departamento principal<select required value={form.primary_department_id ?? ""} onChange={e => setForm({ ...form, primary_department_id: Number(e.target.value) })}><option value="">Selecciona un departamento</option>{departments.filter(d => form.department_ids.includes(d.id)).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select><small>El campus se obtiene del departamento principal.</small></label>
        </>}{formError && <p role="alert" className={styles.error}>{formError}</p>}<div className={styles.formActions}><button type="button" className="secondary-button" disabled={saving} onClick={close}>Cancelar</button><button className={mode === "delete" ? styles.danger : "primary-button"} disabled={saving || (mode === "delete" ? confirmation !== "ELIMINAR" : !form.department_ids.length)}>{saving ? "Guardando…" : mode === "delete" ? "Eliminar colaborador" : "Guardar colaborador"}</button></div>
      </form>}
    </dialog>
  </section>;
}
