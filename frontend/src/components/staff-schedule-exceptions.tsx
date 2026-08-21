"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { StaffScheduleExceptionHistoryItem, StaffScheduleExceptionHistoryResponse } from "@/lib/auth";

const labels: Record<StaffScheduleExceptionHistoryItem["operation"], string> = {
  entry: "Cambio de entrada",
  exit: "Cambio de salida",
  replace: "Horario completo",
  revoke: "Excepción de horario eliminada",
  holiday_work: "Turno autorizado en descanso oficial",
  attendance_exemption: "Checada justificada",
  legacy: "Excepción vigente sin historial",
};

const intervals = (values: { start: string; end: string }[]) => values.length ? values.map((item) => `${item.start.slice(0, 5)}–${item.end.slice(0, 5)}`).join(" · ") : "Sin horario";

export function StaffScheduleExceptions({ departmentId, employeeId }: { departmentId: number; employeeId: number }) {
  const router = useRouter();
  const [items, setItems] = useState<StaffScheduleExceptionHistoryItem[]>([]);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [message, setMessage] = useState("Cargando excepciones…");
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async (nextOffset = 0, append = false) => {
    setLoading(true); setMessage(append ? "Cargando más…" : "Cargando excepciones…");
    try {
      const query = new URLSearchParams({ department_id: String(departmentId), employee_id: String(employeeId), offset: String(nextOffset), limit: "50" });
      if (startDate) query.set("start_date", startDate);
      if (endDate) query.set("end_date", endDate);
      const response = await fetch(`/api/staff/schedule-exceptions?${query}`, { cache: "no-store" });
      const payload = await response.json() as StaffScheduleExceptionHistoryResponse;
      if (!response.ok) throw new Error((payload as unknown as { detail?: string }).detail ?? "No fue posible cargar las excepciones.");
      setItems((current) => append ? [...current, ...payload.items] : payload.items);
      setOffset(payload.offset + payload.items.length); setHasMore(payload.has_more); setTotal(payload.total);
      setMessage(payload.items.length === 0 && !append ? "No hay excepciones registradas para este colaborador." : "");
    } catch (error) { setMessage(error instanceof Error ? error.message : "No fue posible cargar las excepciones."); }
    finally { setLoading(false); }
  }, [departmentId, employeeId, endDate, startDate]);

  useEffect(() => { void load(); }, [load]);

  const remove = async (item: StaffScheduleExceptionHistoryItem) => {
    if (!item.deletion_kind || !window.confirm(`¿Eliminar la excepción vigente del ${item.target_date}? El historial se conservará.`)) return;
    setDeletingId(item.id); setMessage("");
    try {
      const query = new URLSearchParams({ department_id: String(departmentId), employee_id: String(employeeId), target_date: item.target_date, kind: item.deletion_kind });
      const response = await fetch(`/api/staff/schedule-exceptions?${query}`, { method: "DELETE" });
      if (!response.ok) {
        const payload = await response.json() as { detail?: string };
        throw new Error(payload.detail ?? "No fue posible eliminar la excepción.");
      }
      await load();
      // Actualiza las tarjetas y los contadores renderizados por el servidor,
      // sin forzar una recarga completa ni cerrar el modal.
      router.refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "No fue posible eliminar la excepción."); }
    finally { setDeletingId(null); }
  };

  return <section className="space-y-3">
    <div className="grid gap-3 sm:grid-cols-2"><label className="text-xs font-semibold">Desde<input type="date" className="field-input mt-1 w-full" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label className="text-xs font-semibold">Hasta<input type="date" className="field-input mt-1 w-full" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label></div>
    <button type="button" className="secondary-button px-3 py-2 text-xs" disabled={loading} onClick={() => void load()}>Aplicar filtros</button>
    {total > 0 ? <p className="text-xs text-(--muted)">{total} excepciones registradas.</p> : null}
    {message ? <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-(--muted)">{message}</p> : null}
    <div className="space-y-3">{items.map((item) => <article key={item.id} className="rounded-2xl border border-border p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-sm font-semibold text-(--color-brand-strong)">{item.target_date} · {labels[item.operation]}</p><p className="mt-1 text-xs text-(--muted)">{item.instruction ?? "Sin instrucción registrada"}</p></div><div className="flex items-center gap-2"><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${item.is_current ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{item.is_current ? "Vigente" : "Reemplazada"}</span>{item.deletion_kind ? <button type="button" className="rounded-full border border-rose-200 px-2 py-1 text-[10px] font-bold text-rose-700 hover:bg-rose-50 disabled:opacity-60" disabled={deletingId === item.id} onClick={() => void remove(item)}>{deletingId === item.id ? "Eliminando…" : "Eliminar"}</button> : null}</div></div><div className="mt-3 grid gap-2 text-xs sm:grid-cols-3"><p><span className="block font-semibold text-slate-500">Anterior</span>{intervals(item.previous_intervals)}</p><p><span className="block font-semibold text-slate-500">Aplicado</span>{intervals(item.applied_intervals)}</p><p><span className="block font-semibold text-slate-500">Vigente</span>{intervals(item.current_intervals)}</p></div><p className="mt-3 text-[11px] text-(--muted)">{item.historical_detail_available ? `${item.author_name ?? "Staff no identificado"} · ${item.created_at ? new Date(item.created_at).toLocaleString("es-MX") : "Fecha no disponible"}` : "Registro previo a la bitácora detallada."}</p></article>)}</div>
    {hasMore ? <button type="button" className="secondary-button w-full px-3 py-2 text-xs" disabled={loading} onClick={() => void load(offset, true)}>{loading ? "Cargando…" : "Cargar más"}</button> : null}
  </section>;
}
