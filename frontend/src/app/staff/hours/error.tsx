"use client";

export default function HoursError({ reset }: { reset: () => void }) {
  return <main className="mx-auto max-w-3xl space-y-4 rounded-3xl bg-white p-8">
    <h1 className="text-xl font-bold">No se pudo generar el reporte de horas</h1>
    <p>Verifica la conexión e intenta nuevamente. No se modificó ningún registro.</p>
    <button type="button" className="primary-button px-4 py-3" onClick={reset}>Reintentar</button>
    <a href="/staff" className="ghost-button ml-3 px-4 py-3">Volver a la consulta</a>
  </main>;
}
