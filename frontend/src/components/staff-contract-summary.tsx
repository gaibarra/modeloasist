"use client";
import { useEffect, useState } from "react";
import { ContractReport, ContractRow, contractDuration } from "@/lib/labor-contracts";

export function StaffContractSummary({ departmentId, employeeId, year, semester }: { departmentId: number; employeeId: number; year: number; semester: number }) {
  const [result, setResult] = useState<{ row?: ContractRow; message?: string }>({ message: "Cargando contrato…" });
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/staff/labor-contracts?department_id=${departmentId}&employee_id=${employeeId}&academic_year=${year}&semester=${semester}`, { cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error("No se pudo consultar el contrato");
        const data: ContractReport = await response.json();
        if (!controller.signal.aborted) setResult(data.available ? { row: data.rows[0] } : { message: "Contratos aún no habilitados" });
      }).catch(error => { if (!controller.signal.aborted) setResult({ message: error instanceof Error ? error.message : "Error de consulta" }); });
    return () => controller.abort();
  }, [departmentId, employeeId, year, semester]);
  return <aside className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm" aria-live="polite">
    <strong>Contrato laboral y horario guardado · horas:minutos</strong>
    {result.message ? <p>{result.message}</p> : result.row ? <><p>Contrato: {contractDuration(result.row.contract_minutes)} · Horario semestral: {contractDuration(result.row.scheduled_minutes)} · Diferencia: {contractDuration(result.row.difference_minutes)}</p><p>{result.row.status_label} · {result.row.source_presence}</p><p className="text-xs">No incluye cambios sin guardar ni excepciones de fechas específicas.</p></> : <p>Sin información contractual</p>}
  </aside>;
}
