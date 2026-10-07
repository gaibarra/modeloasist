"use client";
export default function ContractsError({ reset }: { reset: () => void }) {
  return <main className="mx-auto max-w-3xl space-y-4 bg-white p-8"><h1>No se pudo consultar el reporte de contratos</h1><p>No se modificó ningún dato.</p><button type="button" onClick={reset} className="primary-button p-3">Reintentar</button><a href="/staff" className="ghost-button p-3">Volver a asistencia</a></main>;
}
