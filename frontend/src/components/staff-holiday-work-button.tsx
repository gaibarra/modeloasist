"use client";

import { useState } from "react";

export function StaffHolidayWorkButton({ departmentId, employeeId, employeeName, holidayDate, holidayName }: { departmentId: number; employeeId: number; employeeName: string; holidayDate: string; holidayName: string }) {
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState("07:00");
  const [end, setEnd] = useState("15:00");
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (!start || !end || start >= end) return setMessage("La hora de inicio debe ser anterior a la hora de fin.");
    setSaving(true); setMessage(null);
    try {
      const response = await fetch("/api/staff/holiday-work", { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ department_id: departmentId, employee_id: employeeId, holiday_date: holidayDate, intervals: [{ start, end }] }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "No fue posible autorizar el turno.");
      setMessage("Turno autorizado y registrado.");
      window.setTimeout(() => window.location.reload(), 500);
    } catch (error) { setMessage(error instanceof Error ? error.message : "No fue posible autorizar el turno."); }
    finally { setSaving(false); }
  };
  return <>
    <button type="button" className="mt-2 text-[10px] font-bold text-violet-700 underline underline-offset-2" onClick={() => setOpen(true)}>Autorizar turno</button>
    {open && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-3" role="dialog" aria-modal="true"><div className="w-full max-w-sm rounded-3xl bg-white p-5 shadow-2xl"><p className="section-eyebrow">Descanso oficial</p><h2 className="mt-1 text-lg font-semibold text-(--color-brand-strong)">Autorizar turno</h2><p className="mt-1 text-sm text-(--muted)">{employeeName} · {holidayName}</p><div className="mt-4 grid grid-cols-2 gap-3"><label className="text-xs font-semibold">Entrada<input type="time" className="field-input mt-1 w-full" value={start} onChange={(event) => setStart(event.target.value)} /></label><label className="text-xs font-semibold">Salida<input type="time" className="field-input mt-1 w-full" value={end} onChange={(event) => setEnd(event.target.value)} /></label></div>{message ? <p className="mt-3 text-xs text-(--muted)">{message}</p> : null}<div className="mt-5 flex justify-end gap-2"><button type="button" className="secondary-button px-3 py-2 text-xs" onClick={() => setOpen(false)}>Cancelar</button><button type="button" className="primary-button px-3 py-2 text-xs" onClick={save} disabled={saving}>{saving ? "Guardando…" : "Autorizar"}</button></div></div></div>}
  </>;
}
