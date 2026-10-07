export type ContractRow = {
  employee_id: number; employee_name: string; department_id: number; department_name: string;
  campus: string | null; contract_minutes: number | null; scheduled_minutes: number | null;
  difference_minutes: number | null; status: string; status_label: string; source_presence: string;
};
export type ContractReport = { available: boolean; academic_year: number; semester: number; rows: ContractRow[] };
export const contractDuration = (minutes: number | null) => minutes === null ? "—" : `${minutes < 0 ? "−" : ""}${Math.floor(Math.abs(minutes) / 60)}:${String(Math.abs(minutes) % 60).padStart(2, "0")}`;
