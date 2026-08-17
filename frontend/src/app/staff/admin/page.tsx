import Link from "next/link";

import { ChangePasswordLink } from "@/components/change-password-link";
import { InstitutionHeader } from "@/components/institution-header";
import { StaffAdminPanel } from "@/components/staff-admin-panel";
import { LogoutButton } from "@/components/logout-button";
import { AttendanceImportBatchSummary, DepartmentSummary, StaffUserSummary } from "@/lib/auth";
import { BACKEND_API_BASE_URL, SESSION_COOKIE_NAME } from "@/lib/auth";
import { requireAdminUser } from "@/lib/server-session";
import { cookies } from "next/headers";

async function fetchWithToken(path: string) {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return { ok: false, status: 401, body: { detail: "Sesión no encontrada" } };
  }
  const response = await fetch(`${BACKEND_API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({ detail: "Respuesta inválida" }));
  return { ok: response.ok, status: response.status, body };
}

export default async function StaffAdminPage() {
  const user = await requireAdminUser();
  const [departmentsResponse, usersResponse, importsResponse] = await Promise.all([
    fetchWithToken("/staff/departments"),
    fetchWithToken("/staff/users"),
    fetchWithToken("/staff/attendance-imports"),
  ]);

  const initialError = !departmentsResponse.ok
    ? String((departmentsResponse.body as { detail?: string }).detail ?? "No fue posible cargar departamentos")
    : !usersResponse.ok
      ? String((usersResponse.body as { detail?: string }).detail ?? "No fue posible cargar staff")
      : !importsResponse.ok
        ? String((importsResponse.body as { detail?: string }).detail ?? "No fue posible cargar el historial de importaciones")
      : null;

  return (
    <div className="page-shell text-foreground">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <InstitutionHeader
          eyebrow="Superadmin · gestión staff"
          title="Usuarios staff y departamentos"
          description="Crea cuentas operativas y asigna su alcance por departamento para la consulta móvil diaria con una vista institucional más sobria."
          actions={<><ChangePasswordLink /><Link href="/" className="secondary-button">Volver al dashboard</Link><LogoutButton /></>}
        />

        <StaffAdminPanel
          initialDepartments={departmentsResponse.ok ? (departmentsResponse.body as DepartmentSummary[]) : []}
          initialStaffUsers={usersResponse.ok ? (usersResponse.body as StaffUserSummary[]) : []}
          initialAttendanceImports={importsResponse.ok ? (importsResponse.body as AttendanceImportBatchSummary[]) : []}
          isSuperadmin={user.actor_type === "staff" ? user.is_superadmin : false}
          initialError={initialError}
        />
      </div>
    </div>
  );
}