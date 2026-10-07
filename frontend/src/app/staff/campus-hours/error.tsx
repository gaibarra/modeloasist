"use client";
export default function CampusHoursError({ reset }: { reset: () => void }) {
  return <main className="mx-auto max-w-3xl space-y-4 bg-white p-8"><h1 className="text-xl font-bold">No se pudo generar el reporte por campus</h1><p>Comprueba la conexión y vuelve a intentarlo. No se modificó ningún dato.</p><button type="button" className="primary-button p-3" onClick={reset}>Reintentar</button><a className="ghost-button p-3" href="/staff">Volver a asistencia</a></main>;
}
