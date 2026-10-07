export const executiveCampuses = ["Chetumal", "Montejo", "Mérida", "Valladolid"] as const;
export const canViewCampusHours = (email: string) => ["gaibarra@hotmail.com", "duchliz@modelo.edu.mx"].includes(email.trim().toLowerCase());
export type CampusHoursReport = {
  campus: string; start_date: string; end_date: string;
  totals: { employees: number; labor_contract_seconds: number | null; scheduled_seconds: number; worked_seconds: number };
  rows: { employee_id: number; employee_name: string; labor_contract_seconds: number | null;
    scheduled_seconds: number; worked_seconds: number; scheduled_contract_difference_seconds: number | null;
    worked_scheduled_difference_seconds: number; observations: string }[];
};
export function hoursLabel(seconds: number | null) {
  if (seconds === null) return "Sin referencia completa";
  const minutes = Math.round(Math.abs(seconds) / 60);
  return `${seconds < 0 ? "−" : ""}${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}
export function isCompleteWeek(start: string, end: string) {
  if (![start, end].every(value => /^\d{4}-\d{2}-\d{2}$/.test(value))) return false;
  const a = new Date(`${start}T00:00:00Z`), b = new Date(`${end}T00:00:00Z`);
  return Number.isFinite(a.getTime()) && Number.isFinite(b.getTime()) && a.toISOString().slice(0, 10) === start &&
    b.toISOString().slice(0, 10) === end && a.getUTCDay() === 1 && b.getTime() - a.getTime() === 6 * 86400000;
}
