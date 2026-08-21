"use client";

import { Mic, Sparkles, X } from "lucide-react";
import { useRef, useState } from "react";

type Interval = { start: string; end: string };
type Change = { employee_id: number; employee_name: string; target_date: string; previous_intervals: Interval[]; new_intervals: Interval[] };
type Exclusion = { employee_id: number; employee_name: string; target_date: string; reason: string };
type Preview = { affected_employees: number; changes: Change[]; exclusions: Exclusion[]; preview_token: string };

type Recognition = { lang: string; continuous: boolean; interimResults: boolean; start(): void; stop(): void; onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onerror: (() => void) | null; onend: (() => void) | null };
type RecognitionConstructor = new () => Recognition;

function formatIntervals(intervals: Interval[]) {
  return intervals.map((item) => `${item.start.slice(0, 5)}–${item.end.slice(0, 5)}`).join(" · ");
}

export function StaffScheduleBulkDialog({ departmentId, departmentName }: { departmentId: number; departmentName: string }) {
  const [open, setOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<Recognition | null>(null);

  const close = () => { recognitionRef.current?.stop(); setOpen(false); setPreview(null); setMessage(null); setListening(false); };
  const interpret = async () => {
    setLoading(true); setMessage(null); setPreview(null);
    try {
      const response = await fetch("/api/staff/schedule-bulk/preview", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ department_id: departmentId, instruction }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "No fue posible interpretar la instrucción.");
      setPreview(data);
    } catch (error) { setMessage(error instanceof Error ? error.message : "No fue posible interpretar la instrucción."); }
    finally { setLoading(false); }
  };
  const apply = async () => {
    if (!preview) return;
    setLoading(true); setMessage(null);
    try {
      const response = await fetch("/api/staff/schedule-bulk/apply", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ preview_token: preview.preview_token }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "No fue posible aplicar los cambios.");
      setMessage(`Cambios aplicados: ${data.changed_days} días para ${data.affected_employees} colaboradores.`);
      setPreview(null);
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) { setMessage(error instanceof Error ? error.message : "No fue posible aplicar los cambios."); }
    finally { setLoading(false); }
  };
  const dictate = () => {
    const Constructor = (window as typeof window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }).SpeechRecognition
      ?? (window as typeof window & { webkitSpeechRecognition?: RecognitionConstructor }).webkitSpeechRecognition;
    if (!Constructor) { setMessage("El dictado no está disponible en este navegador. Puedes escribir la instrucción."); return; }
    const recognition = new Constructor(); recognition.lang = "es-MX"; recognition.continuous = false; recognition.interimResults = false;
    recognition.onresult = (event) => setInstruction((current) => `${current}${current ? " " : ""}${event.results[0][0].transcript}`);
    recognition.onerror = () => setMessage("No fue posible transcribir el audio. Revisa el permiso del micrófono o escribe la instrucción.");
    recognition.onend = () => setListening(false); recognitionRef.current = recognition; setListening(true); recognition.start();
  };
  return <>
    <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"><Sparkles className="h-4 w-4" />Cambio de horarios</button>
    {open && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Cambio masivo de horario">
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-[28px] bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-border px-6 py-5"><div><p className="section-eyebrow">Cambio de horarios</p><h2 className="text-xl font-semibold text-(--color-brand-strong)">{departmentName}</h2><p className="mt-1 text-sm text-(--muted)">Solo modifica colaboradores del departamento activo. Primero revisa la propuesta.</p></div><button type="button" className="secondary-button rounded-full p-2" onClick={close} aria-label="Cerrar"><X className="h-4 w-4" /></button></header>
        <div className="space-y-4 overflow-y-auto px-6 py-5">
          <label className="block text-sm font-semibold text-slate-800">Instrucción<textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Del 17 al 23 de agosto la entrada para todos será a las 9 am" className="field-input mt-2 min-h-24 w-full resize-y" /></label>
          <div className="flex flex-wrap items-center gap-2"><button type="button" onClick={dictate} disabled={listening} className="secondary-button inline-flex items-center gap-2 px-3 py-2 text-xs"><Mic className="h-4 w-4" />{listening ? "Escuchando…" : "Dictar instrucción"}</button><span className="text-xs text-(--muted)">Ejemplos: “entrada para todos a las 9 am”, “salida para todos a las 3 pm”, “horario para todos de 9 am a 3 pm”.</span></div>
          {!preview && <button type="button" onClick={interpret} disabled={loading || instruction.trim().length < 8} className="primary-button px-4 py-2 text-sm">{loading ? "Interpretando…" : "Ver vista previa"}</button>}
          {message && <p className="rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-700">{message}</p>}
          {preview && <section className="space-y-3"><div className="rounded-2xl border border-indigo-100 bg-indigo-50 p-4 text-sm text-indigo-950"><strong>{preview.affected_employees} colaboradores</strong> y <strong>{preview.changes.length} días</strong> serán modificados. Las exclusiones no crearán turnos en días de descanso.</div><div className="overflow-x-auto rounded-2xl border border-border"><table className="min-w-full text-left text-xs"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-3 py-2">Fecha</th><th className="px-3 py-2">Colaborador</th><th className="px-3 py-2">Horario anterior</th><th className="px-3 py-2">Nuevo horario</th></tr></thead><tbody>{preview.changes.map((change) => <tr key={`${change.employee_id}-${change.target_date}`} className="border-t border-border"><td className="whitespace-nowrap px-3 py-2">{change.target_date}</td><td className="px-3 py-2 font-medium">{change.employee_name}</td><td className="whitespace-nowrap px-3 py-2">{formatIntervals(change.previous_intervals)}</td><td className="whitespace-nowrap px-3 py-2 font-semibold text-indigo-800">{formatIntervals(change.new_intervals)}</td></tr>)}</tbody></table></div>{preview.exclusions.length > 0 && <p className="text-xs text-(--muted)">{preview.exclusions.length} exclusiones: días sin horario registrado o cambios que producirían traslapes.</p>}</section>}
        </div>
        <footer className="flex justify-end gap-3 border-t border-border px-6 py-4"><button type="button" className="secondary-button px-4 py-2" onClick={close}>Cancelar</button>{preview && <button type="button" className="primary-button px-4 py-2" disabled={loading} onClick={apply}>{loading ? "Aplicando…" : `Aplicar cambios a ${preview.affected_employees} colaboradores`}</button>}</footer>
      </div>
    </div>}
  </>;
}
