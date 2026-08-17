"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  AttendanceImportBatchSummary,
  AttendanceImportResult,
  DepartmentSummary,
  StaffUserCreateRequest,
  StaffUserSummary,
} from "@/lib/auth";

type StaffAdminPanelProps = {
  initialDepartments: DepartmentSummary[];
  initialStaffUsers: StaffUserSummary[];
  initialAttendanceImports: AttendanceImportBatchSummary[];
  isSuperadmin: boolean;
  initialError?: string | null;
};

type CreateFormState = {
  email: string;
  full_name: string;
  password: string;
  employee_id: string;
  department_ids: number[];
  is_superadmin: boolean;
  must_change_password: boolean;
};

const INITIAL_FORM: CreateFormState = {
  email: "",
  full_name: "",
  password: "",
  employee_id: "",
  department_ids: [],
  is_superadmin: false,
  must_change_password: true,
};

async function readApiPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { detail: text };
  }
}

function getApiErrorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === "object") {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) {
        return message;
      }
    }
  }
  return fallback;
}

export function StaffAdminPanel({
  initialDepartments,
  initialStaffUsers,
  initialAttendanceImports,
  isSuperadmin,
  initialError = null,
}: StaffAdminPanelProps) {
  const [departments, setDepartments] = useState(initialDepartments);
  const [staffUsers, setStaffUsers] = useState(initialStaffUsers);
  const [attendanceImports, setAttendanceImports] = useState(initialAttendanceImports);
  const [form, setForm] = useState<CreateFormState>(INITIAL_FORM);
  const [error, setError] = useState<string | null>(initialError);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingDepartmentsFor, setSavingDepartmentsFor] = useState<number | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<AttendanceImportResult | null>(null);

  const sortedDepartments = useMemo(
    () => [...departments].sort((a, b) => `${a.campus ?? ""}${a.name}`.localeCompare(`${b.campus ?? ""}${b.name}`)),
    [departments],
  );

  useEffect(() => {
    setDepartments(initialDepartments);
    setStaffUsers(initialStaffUsers);
    setAttendanceImports(initialAttendanceImports);
    setError(initialError);
  }, [initialAttendanceImports, initialDepartments, initialStaffUsers, initialError]);

  const reloadData = async () => {
    const [departmentsResponse, usersResponse, importsResponse] = await Promise.all([
      fetch("/api/staff/departments", { cache: "no-store" }),
      fetch("/api/staff/users", { cache: "no-store" }),
      fetch("/api/staff/attendance-imports", { cache: "no-store" }),
    ]);
    const departmentsPayload = await departmentsResponse.json();
    const usersPayload = await usersResponse.json();
    const importsPayload = await importsResponse.json();
    if (!departmentsResponse.ok) {
      throw new Error(departmentsPayload.detail ?? "No fue posible recargar departamentos");
    }
    if (!usersResponse.ok) {
      throw new Error(usersPayload.detail ?? "No fue posible recargar staff");
    }
    if (!importsResponse.ok) {
      throw new Error(importsPayload.detail ?? "No fue posible recargar importaciones");
    }
    setDepartments(departmentsPayload as DepartmentSummary[]);
    setStaffUsers(usersPayload as StaffUserSummary[]);
    setAttendanceImports(importsPayload as AttendanceImportBatchSummary[]);
  };

  const handleDepartmentToggle = (departmentId: number, checked: boolean) => {
    setForm((current) => ({
      ...current,
      department_ids: checked
        ? [...current.department_ids, departmentId].sort((a, b) => a - b)
        : current.department_ids.filter((id) => id !== departmentId),
    }));
  };

  const handleCreateStaff = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: StaffUserCreateRequest = {
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        password: form.password,
        employee_id: form.employee_id ? Number(form.employee_id) : null,
        department_ids: form.department_ids,
        is_superadmin: form.is_superadmin,
        must_change_password: form.must_change_password,
      };
      const response = await fetch("/api/staff/users", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.detail ?? "No fue posible crear el usuario staff");
      }
      await reloadData();
      setForm(INITIAL_FORM);
      setSuccess("Usuario staff creado correctamente");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  const updateUserDepartments = async (staffUserId: number, departmentIds: number[]) => {
    setSavingDepartmentsFor(staffUserId);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(`/api/staff/users/${staffUserId}/departments`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ department_ids: departmentIds }),
      });
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.detail ?? "No fue posible actualizar departamentos");
      }
      setStaffUsers((current) => current.map((item) => (item.id === staffUserId ? (body as StaffUserSummary) : item)));
      setSuccess("Departamentos actualizados");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
    } finally {
      setSavingDepartmentsFor(null);
    }
  };

  const handleUploadAttendance = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      setError("Selecciona un archivo .xlsx para importar");
      return;
    }
    setUploadingFile(true);
    setError(null);
    setSuccess(null);
    setImportResult(null);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const response = await fetch("/api/staff/attendance-imports", {
        method: "POST",
        body: formData,
      });
      const body = await readApiPayload(response);
      if (!response.ok) {
        throw new Error(getApiErrorMessage(body, "No fue posible importar el archivo"));
      }
      setImportResult(body as AttendanceImportResult);
      await reloadData();
      setSelectedFile(null);
      setSuccess("Archivo importado correctamente");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
    } finally {
      setUploadingFile(false);
    }
  };

  const latestImportResult = importResult?.batch ?? null;
  const latestNameSearchFailures = latestImportResult?.auto_created_employees.filter((employee) => employee.lookup_reason !== "employee_id_not_found") ?? [];

  return (
    <div className="space-y-6">
      {error ? (
        <div className="alert-error">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="alert-success">
          {success}
        </div>
      ) : null}

      {isSuperadmin ? (
        <section className="surface-card p-6">
          <div className="mb-5">
            <p className="section-eyebrow">Carga diaria</p>
            <h2 className="text-2xl font-semibold text-(--color-brand-strong)">Importar asistencia desde Excel</h2>
            <p className="mt-2 max-w-3xl text-sm text-(--muted)">
              Sube el archivo diario en formato fijo `.xlsx`. El sistema ignorará registros repetidos,
              auto-creará empleados faltantes y dejará trazabilidad del lote procesado.
            </p>
          </div>

          <form onSubmit={handleUploadAttendance} className="space-y-5">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
              <div className="surface-muted space-y-3 px-4 py-4">
                <p className="text-sm font-medium text-foreground">Plantilla esperada</p>
                <ul className="space-y-1 text-sm text-(--muted)">
                  <li>Archivo `.xlsx` con encabezados fijos como el formato operativo actual.</li>
                  <li>Columnas críticas: `nombre`, `ID`, `departamento`, `Fecha`, `Tiempo`, `Fuente de datos`, `Nombre del dispositivo`, `N.º de serie del dispositivo`.</li>
                  <li>Si un `ID` no existe en `employees`, se crea automáticamente con correo provisional.</li>
                </ul>
              </div>
              <div className="surface-muted space-y-4 px-4 py-4">
                <Field label="Archivo Excel (.xlsx)">
                  <input
                    type="file"
                    accept=".xlsx"
                    className="field-input file:mr-3 file:rounded-full file:border-0 file:bg-(--color-brand-strong) file:px-4 file:py-2 file:text-sm file:font-medium file:text-white"
                    onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                  />
                </Field>
                <div className="text-sm text-(--muted)">
                  {selectedFile ? `Seleccionado: ${selectedFile.name}` : "Aún no has seleccionado un archivo."}
                </div>
                <button
                  type="submit"
                  disabled={uploadingFile || !selectedFile}
                  className="primary-button disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {uploadingFile ? "Importando..." : "Subir e importar"}
                </button>
              </div>
            </div>
          </form>

          {latestImportResult ? (
            <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <article className="surface-muted px-4 py-4">
                <h3 className="text-base font-semibold text-foreground">Resultado del último lote</h3>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm text-(--muted)">
                  <Metric label="Archivo" value={latestImportResult.original_filename} />
                  <Metric label="Filas leídas" value={String(latestImportResult.total_rows)} />
                  <Metric label="Importadas" value={String(latestImportResult.imported_rows)} />
                  <Metric label="Duplicados" value={String(latestImportResult.skipped_duplicates)} />
                  <Metric label="Inválidas" value={String(latestImportResult.invalid_rows)} />
                  <Metric label="Empleados nuevos" value={String(latestImportResult.auto_created_employees.length)} />
                </dl>
                <div className="mt-4 space-y-2 text-sm text-(--muted)">
                  <p className="font-medium text-foreground">Desglose de duplicados</p>
                  {latestImportResult.duplicate_breakdown.length === 0 ? (
                    <p>No hubo duplicados en este lote.</p>
                  ) : (
                    latestImportResult.duplicate_breakdown.map((item) => (
                      <p key={item.reason}>{item.label}: {item.count}</p>
                    ))
                  )}
                </div>
              </article>

              <article className="surface-muted px-4 py-4">
                <h3 className="text-base font-semibold text-foreground">Empleados auto-creados</h3>
                <p className="mt-3 text-sm text-(--muted)">
                  Buscados por nombre sin éxito: {latestNameSearchFailures.length}
                </p>
                {latestImportResult.auto_created_employees.length === 0 ? (
                  <p className="mt-3 text-sm text-(--muted)">Este lote no necesitó altas automáticas.</p>
                ) : (
                  <div className="mt-3 space-y-3 text-sm">
                    {latestImportResult.auto_created_employees.map((employee) => (
                      <div key={employee.employee_id} className="surface-card bg-white px-3 py-3 shadow-none">
                        <p className="font-medium text-foreground">{employee.nombre}</p>
                        <p className="text-(--muted)">ID {employee.employee_id} · {employee.departamento}</p>
                        <p className="text-(--muted)">{employee.email}</p>
                        <p className="text-(--muted)">{employee.lookup_label}</p>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            </div>
          ) : null}

          {importResult?.row_errors.length ? (
            <div className="mt-6 surface-muted px-4 py-4">
              <h3 className="text-base font-semibold text-foreground">Filas con observaciones</h3>
              <div className="mt-3 space-y-2 text-sm text-(--muted)">
                {importResult.row_errors.map((rowError) => (
                  <p key={`${rowError.row_number}-${rowError.message}`}>
                    Fila {rowError.row_number}: {rowError.message}
                  </p>
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-6">
            <div className="mb-4">
              <p className="section-eyebrow">Historial reciente</p>
              <h3 className="text-xl font-semibold text-(--color-brand-strong)">Últimas importaciones</h3>
            </div>
            {attendanceImports.length === 0 ? (
              <div className="surface-muted border-dashed px-4 py-5 text-sm text-(--muted)">
                Aún no hay lotes de importación registrados.
              </div>
            ) : (
              <div className="space-y-3">
                {attendanceImports.map((batch) => (
                  <article key={batch.id} className="surface-muted px-4 py-4 text-sm">
                    <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                      <div>
                        <p className="font-medium text-foreground">{batch.original_filename}</p>
                        <p className="text-(--muted)">
                          {new Date(batch.uploaded_at).toLocaleString("es-MX")} · {batch.uploaded_by ?? "Sin registro"}
                        </p>
                      </div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-(--muted) md:text-right">
                        <span>Total: {batch.total_rows}</span>
                        <span>Importadas: {batch.imported_rows}</span>
                        <span>Duplicados: {batch.skipped_duplicates}</span>
                        <span>Nuevos: {batch.auto_created_employees.length}</span>
                      </div>
                    </div>
                    {batch.duplicate_breakdown.length > 0 ? (
                      <p className="mt-3 text-(--muted)">
                        {batch.duplicate_breakdown[0].label}: {batch.duplicate_breakdown[0].count}
                      </p>
                    ) : null}
                    {batch.auto_created_employees.length > 0 ? (
                      <p className="mt-1 text-(--muted)">
                        Buscados por nombre sin éxito: {batch.auto_created_employees.filter((employee) => employee.lookup_reason !== "employee_id_not_found").length}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
      ) : null}

      <section className="surface-card p-6">
        <div className="mb-5">
          <p className="section-eyebrow">Alta de staff</p>
          <h2 className="text-2xl font-semibold text-(--color-brand-strong)">Crear usuario staff</h2>
        </div>
        <form onSubmit={handleCreateStaff} className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Correo">
              <input value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} type="email" required className="field-input" placeholder="staff@modelo.edu.mx" />
            </Field>
            <Field label="Nombre completo">
              <input value={form.full_name} onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))} type="text" required className="field-input" placeholder="Nombre del staff" />
            </Field>
            <Field label="Contraseña inicial">
              <input value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} type="text" minLength={8} required className="field-input" placeholder="Genera una contraseña temporal única" />
            </Field>
            <Field label="Employee ID opcional">
              <input value={form.employee_id} onChange={(event) => setForm((current) => ({ ...current, employee_id: event.target.value }))} type="number" min={1} className="field-input" placeholder="Ej. 123" />
            </Field>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="surface-muted inline-flex items-center gap-3 px-4 py-3 text-sm text-foreground">
              <input type="checkbox" checked={form.is_superadmin} onChange={(event) => setForm((current) => ({ ...current, is_superadmin: event.target.checked }))} />
              Superadmin
            </label>
            <label className="surface-muted inline-flex items-center gap-3 px-4 py-3 text-sm text-foreground">
              <input type="checkbox" checked={form.must_change_password} onChange={(event) => setForm((current) => ({ ...current, must_change_password: event.target.checked }))} />
              Forzar cambio de contraseña
            </label>
          </div>

          <div>
            <p className="mb-3 text-sm font-medium text-foreground">Departamentos asignados</p>
            {sortedDepartments.length === 0 ? (
              <div className="surface-muted border-dashed px-4 py-5 text-sm text-(--muted)">
                Aún no hay departamentos disponibles. Si la migración de permisos no se ha aplicado en PostgreSQL, primero hay que resolver ese paso.
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {sortedDepartments.map((department) => {
                  const checked = form.department_ids.includes(department.id);
                  return (
                    <label key={department.id} className="surface-muted flex items-start gap-3 px-4 py-3 text-sm text-foreground">
                      <input type="checkbox" checked={checked} onChange={(event) => handleDepartmentToggle(department.id, event.target.checked)} />
                      <span>
                        <span className="block font-medium text-foreground">{department.name}</span>
                        <span className="text-xs text-(--muted)">{department.campus ?? "Sin campus"}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          <button type="submit" disabled={loading || sortedDepartments.length === 0} className="primary-button disabled:cursor-not-allowed disabled:opacity-60">
            {loading ? "Creando..." : "Crear staff"}
          </button>
        </form>
      </section>

      <section className="surface-card p-6">
        <div className="mb-5">
          <p className="section-eyebrow">Usuarios actuales</p>
          <h2 className="text-2xl font-semibold text-(--color-brand-strong)">Gestión de accesos</h2>
        </div>
        <div className="space-y-4">
          {staffUsers.length === 0 ? (
            <div className="surface-muted border-dashed px-4 py-5 text-sm text-(--muted)">
              Aún no hay usuarios staff creados.
            </div>
          ) : (
            staffUsers.map((user) => (
              <StaffUserCard
                key={`${user.id}-${user.departments.map((department) => department.id).join("-")}`}
                user={user}
                departments={sortedDepartments}
                saving={savingDepartmentsFor === user.id}
                onSave={updateUserDepartments}
              />
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.2em] text-(--muted)">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-foreground">{value}</dd>
    </div>
  );
}

function StaffUserCard({
  user,
  departments,
  saving,
  onSave,
}: {
  user: StaffUserSummary;
  departments: DepartmentSummary[];
  saving: boolean;
  onSave: (staffUserId: number, departmentIds: number[]) => Promise<void>;
}) {
  const [selectedDepartments, setSelectedDepartments] = useState<number[]>(user.departments.map((department) => department.id));
  const [isDepartmentEditorOpen, setIsDepartmentEditorOpen] = useState(false);

  return (
    <article className="surface-muted p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-foreground">{user.full_name}</h3>
          <p className="text-sm text-(--muted)">{user.email}</p>
          <p className="mt-1 text-xs text-(--muted)">
            {user.is_superadmin ? "Superadmin" : "Staff operativo"} · {user.must_change_password ? "Debe cambiar contraseña" : "Contraseña activa"}
          </p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
        <p className="text-sm text-(--muted)">
          {user.is_superadmin ? "Acceso a todos los departamentos" : `${selectedDepartments.length} departamento${selectedDepartments.length === 1 ? "" : "s"} asignado${selectedDepartments.length === 1 ? "" : "s"}`}
        </p>
        {!user.is_superadmin ? (
          <button type="button" className="secondary-button px-4 py-2 text-sm" onClick={() => setIsDepartmentEditorOpen((current) => !current)} aria-expanded={isDepartmentEditorOpen}>
            {isDepartmentEditorOpen ? "Ocultar departamentos" : "Ver departamentos"}
          </button>
        ) : null}
      </div>
      {isDepartmentEditorOpen ? (
        <div className="mt-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {departments.map((department) => {
              const checked = selectedDepartments.includes(department.id);
              return (
                <label key={`${user.id}-${department.id}`} className="surface-card flex items-start gap-3 bg-white px-4 py-3 text-sm shadow-none">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) =>
                      setSelectedDepartments((current) =>
                        event.target.checked
                          ? [...current, department.id].sort((a, b) => a - b)
                          : current.filter((id) => id !== department.id),
                      )
                    }
                    disabled={saving}
                  />
                  <span>
                    <span className="block font-medium text-foreground">{department.name}</span>
                    <span className="text-xs text-(--muted)">{department.campus ?? "Sin campus"}</span>
                  </span>
                </label>
              );
            })}
          </div>
          <div className="mt-4 flex justify-end">
            <button type="button" onClick={() => onSave(user.id, selectedDepartments)} disabled={saving || departments.length === 0} className="secondary-button disabled:cursor-not-allowed disabled:opacity-60">
              {saving ? "Guardando..." : "Guardar departamentos"}
            </button>
          </div>
        </div>
      ) : null}
    </article>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-2 text-sm font-medium text-foreground">
      <span>{label}</span>
      {children}
    </label>
  );
}
