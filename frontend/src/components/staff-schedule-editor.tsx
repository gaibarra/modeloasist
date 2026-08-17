"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import type { StaffSemesterScheduleDay } from "@/lib/auth";

const DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const current = new Date();
const initialSemester = current.getMonth() >= 7 ? 2 : 1;

type Props = { employeeId: number; employeeName: string; departmentId: number };
type Block = { start: string; end: string };

export function StaffScheduleEditor({ employeeId, employeeName, departmentId }: Props) {
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(current.getFullYear());
  const [semester, setSemester] = useState(initialSemester);
  const [days, setDays] = useState<Block[][]>(Array.from({ length: 7 }, () => []));
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStatus("Cargando horario…");
    fetch(`/api/staff/schedules?department_id=${departmentId}&employee_id=${employeeId}&academic_year=${year}&semester=${semester}`, { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail ?? "No fue posible cargar el horario.");
        const next = Array.from({ length: 7 }, () => [] as Block[]);
        for (const day of payload.days as StaffSemesterScheduleDay[]) next[day.weekday] = day.intervals.map((item) => ({ start: item.start.slice(0, 5), end: item.end.slice(0, 5) }));
        setDays(next);
        setStatus(payload.is_manual ? "Horario registrado: puedes editar sus bloques y guardar los cambios." : payload.copied_from_semester ? `Horario precargado del semestre ${payload.copied_from_semester === 1 ? "enero–junio" : "agosto–diciembre"} ${payload.copied_from_academic_year}. Guárdalo para registrarlo en este semestre.` : "Aún no hay un horario manual para este semestre.");
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : "No fue posible cargar el horario."));
  }, [open, departmentId, employeeId, year, semester]);

  const updateBlock = (day: number, index: number, field: keyof Block, value: string) => setDays((currentDays) => currentDays.map((blocks, dayIndex) => dayIndex === day ? blocks.map((block, blockIndex) => blockIndex === index ? { ...block, [field]: value } : block) : blocks));
  const removeBlock = (day: number, index: number) => setDays((currentDays) => currentDays.map((blocks, dayIndex) => dayIndex === day ? blocks.filter((_, blockIndex) => blockIndex !== index) : blocks));
  const addBlock = (day: number) => setDays((currentDays) => currentDays.map((blocks, dayIndex) => dayIndex === day ? [...blocks, { start: "07:00", end: "15:00" }] : blocks));

  const save = async () => {
    for (const blocks of days) for (const block of blocks) if (!block.start || !block.end || block.start >= block.end) return setStatus("Cada bloque debe tener una hora inicial anterior a la final.");
    setSaving(true); setStatus(null);
    const payload = { academic_year: year, semester, days: days.map((intervals, weekday) => ({ weekday, intervals })) };
    try {
      const response = await fetch(`/api/staff/schedules?department_id=${departmentId}&employee_id=${employeeId}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "No fue posible guardar el horario.");
      setOpen(false); window.location.reload();
    } catch (error) { setStatus(error instanceof Error ? error.message : "No fue posible guardar el horario."); }
    finally { setSaving(false); }
  };

  return <>
    <button type="button" className="rounded-full border border-amber-500 bg-amber-400 px-4 py-2 text-xs font-bold text-slate-950 shadow-sm transition hover:bg-amber-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2" onClick={() => setOpen(true)}>Gestionar horario</button>
    {open && <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/30 px-3 py-6 backdrop-blur-sm sm:items-center" role="dialog" aria-modal="true" aria-label="Gestionar horario">
      <div className="w-full max-w-2xl overflow-hidden rounded-[28px] border border-white bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-border px-5 py-4"><div><p className="section-eyebrow">Horario semestral</p><h2 className="text-xl font-semibold text-(--color-brand-strong)">{employeeName}</h2><p className="text-sm text-(--muted)">Define uno o varios bloques por día.</p></div><button className="secondary-button rounded-full p-2" onClick={() => setOpen(false)} aria-label="Cerrar"><X className="h-4 w-4" /></button></header>
        <div className="max-h-[70vh] space-y-4 overflow-y-auto px-5 py-4">
          <div className="grid grid-cols-2 gap-3"><label className="text-sm font-semibold">Año<select className="field-input mt-1 w-full" value={year} onChange={(event) => setYear(Number(event.target.value))}>{[current.getFullYear() - 1, current.getFullYear(), current.getFullYear() + 1].map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-sm font-semibold">Semestre<select className="field-input mt-1 w-full" value={semester} onChange={(event) => setSemester(Number(event.target.value))}><option value={1}>Enero – Junio</option><option value={2}>Agosto – Diciembre</option></select></label></div>
          {DAYS.map((label, day) => <section key={label} className="rounded-2xl border border-border p-3"><div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold text-(--color-brand-strong)">{label}</h3><button type="button" className="text-xs font-semibold text-(--color-brand)" onClick={() => addBlock(day)}><Plus className="mr-1 inline h-3.5 w-3.5" />Agregar bloque</button></div>{days[day].length === 0 ? <p className="text-xs text-(--muted)">Sin horario.</p> : <div className="space-y-2">{days[day].map((block, index) => <div key={index} className="flex items-center gap-2"><input className="field-input w-full" type="time" value={block.start} onChange={(event) => updateBlock(day, index, "start", event.target.value)} /><span>–</span><input className="field-input w-full" type="time" value={block.end} onChange={(event) => updateBlock(day, index, "end", event.target.value)} /><button type="button" className="p-2 text-rose-600" onClick={() => removeBlock(day, index)} aria-label="Eliminar bloque"><Trash2 className="h-4 w-4" /></button></div>)}</div>}</section>)}
          {status && <p className="text-sm text-(--muted)">{status}</p>}
        </div>
        <footer className="flex justify-end gap-3 border-t border-border px-5 py-4"><button className="secondary-button px-4 py-2" onClick={() => setOpen(false)}>Cancelar</button><button className="primary-button px-4 py-2" disabled={saving} onClick={save}>{saving ? "Guardando…" : "Guardar horario"}</button></footer>
      </div>
    </div>}
  </>;
}
