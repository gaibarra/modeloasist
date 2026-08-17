function normalizeBackendApiBaseUrl(value: string) {
  const trimmed = value.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/api") ? trimmed.slice(0, -4) : trimmed;
}

export const BACKEND_API_BASE_URL = normalizeBackendApiBaseUrl(
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8081",
);

export const SESSION_COOKIE_NAME = "modeloasist_session";

export type AuthEmployee = {
  id: number;
  nombre: string;
  email: string;
  departamento: string;
  campus: string | null;
  must_change_password: boolean;
  is_admin: boolean;
};

export type AuthStaff = {
  id: number;
  email: string;
  full_name: string;
  employee_id: number | null;
  must_change_password: boolean;
  is_superadmin: boolean;
  department_ids: number[];
};

export type AuthSubjectResponse =
  | {
      actor_type: "employee";
      employee: AuthEmployee;
      staff: null;
    }
  | {
      actor_type: "staff";
      employee: null;
      staff: AuthStaff;
    };

export type SessionEmployeeUser = AuthEmployee & {
  actor_type: "employee";
};

export type SessionStaffUser = AuthStaff & {
  actor_type: "staff";
};

export type SessionUser = SessionEmployeeUser | SessionStaffUser;

export type LoginResponse =
  | {
      access_token: string;
      token_type: "bearer";
      actor_type: "employee";
      employee: AuthEmployee;
      staff: null;
    }
  | {
      access_token: string;
      token_type: "bearer";
      actor_type: "staff";
      employee: null;
      staff: AuthStaff;
    };

export type ChangePasswordResponse = AuthEmployee | AuthStaff;

export type WeeklyCheckinDay = {
  weekday: number;
  entrada: string | null;
  is_late: boolean | null;
  expected: string | null;
  inferred: boolean;
};

export type EmployeeWeeklyCheckin = {
  week_start: string;
  week_end: string;
  days: WeeklyCheckinDay[];
};

export type AttendanceRecordEvent = {
  id: number;
  fecha: string;
  tiempo: string;
  event_ts: string;
  device_name: string | null;
  device_serial: string | null;
  source: string | null;
};

export type AttendanceRecordSummary = {
  total_days: number;
  late_days: number;
  punctuality_rate: number;
  expected_entry_time: string | null;
};

export type SelfAttendanceRecordResponse = {
  employee: AuthEmployee;
  summary: AttendanceRecordSummary;
  weekly_checkins: EmployeeWeeklyCheckin[];
  recent_events: AttendanceRecordEvent[];
};

export type DepartmentSummary = {
  id: number;
  code: string;
  name: string;
  campus: string | null;
  active: boolean;
};

export type StaffMobilePeriodDay = {
  date: string;
  first_event: string | null;
  last_event: string | null;
  entry_event: string | null;
  exit_event: string | null;
  entry_event_inferred: boolean;
  exit_event_inferred: boolean;
  total_events: number;
  scheduled_start: string | null;
  scheduled_end: string | null;
  schedule_intervals: StaffScheduleInterval[];
  has_mixed_schedule: boolean;
  status: "on_time" | "late" | "left_early" | "absence" | "no_schedule" | "no_events";
};

export type StaffMobilePeriodRow = {
  employee_id: number;
  employee_name: string;
  employee_email: string | null;
  department_id: number;
  department_name: string;
  campus: string | null;
  total_events: number;
  active_days: number;
  period_start: string;
  period_end: string;
  days: StaffMobilePeriodDay[];
};

export type StaffDefaultWeek = {
  latest_event_date: string | null;
  start_date: string;
  end_date: string;
};

export type StaffDepartmentEmployeeSummary = {
  id: number;
  name: string;
  email: string | null;
  campus: string | null;
};

export type StaffScheduleInterval = {
  start: string;
  end: string;
};

export type StaffEmployeeYearWeekDay = {
  date: string;
  first_event: string | null;
  last_event: string | null;
  entry_event: string | null;
  exit_event: string | null;
  entry_event_inferred: boolean;
  exit_event_inferred: boolean;
  total_events: number;
  scheduled_start: string | null;
  scheduled_end: string | null;
  schedule_intervals: StaffScheduleInterval[];
  has_mixed_schedule: boolean;
  status: "on_time" | "late" | "left_early" | "absence" | "no_schedule" | "no_events";
};

export type StaffEmployeeYearWeek = {
  week_start: string;
  week_end: string;
  active_days: number;
  total_events: number;
  days: StaffEmployeeYearWeekDay[];
};

export type StaffEmployeeYearSummary = {
  employee_id: number;
  employee_name: string;
  employee_email: string | null;
  campus: string | null;
  department_id: number;
  department_name: string;
  report_year: number;
  window_start: string;
  window_end: string;
  total_days: number;
  late_days: number;
  punctuality_rate: number;
  registered_schedule_intervals: StaffScheduleInterval[];
  weeks: StaffEmployeeYearWeek[];
};

export type StaffUserSummary = {
  id: number;
  email: string;
  full_name: string;
  employee_id: number | null;
  is_active: boolean;
  is_superadmin: boolean;
  must_change_password: boolean;
  departments: DepartmentSummary[];
};

export type StaffUserCreateRequest = {
  email: string;
  full_name: string;
  password: string;
  employee_id: number | null;
  department_ids: number[];
  is_superadmin: boolean;
  must_change_password: boolean;
};

export type AttendanceImportAutoCreatedEmployee = {
  employee_id: number;
  nombre: string;
  departamento: string;
  email: string;
  lookup_reason: string;
  lookup_label: string;
};

export type AttendanceImportDuplicateReason = {
  reason: string;
  label: string;
  count: number;
};

export type AttendanceImportRowError = {
  row_number: number;
  message: string;
};

export type AttendanceImportBatchSummary = {
  id: string;
  original_filename: string;
  uploaded_at: string;
  uploaded_by: string | null;
  total_rows: number;
  imported_rows: number;
  skipped_duplicates: number;
  invalid_rows: number;
  duplicate_breakdown: AttendanceImportDuplicateReason[];
  auto_created_employees: AttendanceImportAutoCreatedEmployee[];
};

export type AttendanceImportResult = {
  batch: AttendanceImportBatchSummary;
  row_errors: AttendanceImportRowError[];
};

export function resolveSessionUser(payload: AuthSubjectResponse | LoginResponse): SessionUser {
  if (payload.actor_type === "staff") {
    return {
      actor_type: "staff",
      ...payload.staff,
    };
  }
  return {
    actor_type: "employee",
    ...payload.employee,
  };
}

export function resolvePasswordChangeUser(payload: ChangePasswordResponse): SessionUser {
  if ("full_name" in payload) {
    return {
      actor_type: "staff",
      ...payload,
    };
  }
  return {
    actor_type: "employee",
    ...payload,
  };
}

export function getUserMustChangePassword(user: SessionUser): boolean {
  return user.must_change_password;
}

export function isAdminSessionUser(user: SessionUser): boolean {
  return user.actor_type === "staff" ? user.is_superadmin : user.is_admin;
}

export function getDefaultRouteForUser(user: SessionUser): string {
  if (user.must_change_password) {
    return "/cambiar-password";
  }
  if (user.actor_type === "staff") {
    return "/staff";
  }
  return user.is_admin ? "/" : "/mi-asistencia";
}