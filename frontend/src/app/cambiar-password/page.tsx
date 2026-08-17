import { redirect } from "next/navigation";
import Link from "next/link";

import { ChangePasswordForm } from "@/components/change-password-form";
import { SchoolLogo } from "@/components/school-logo";
import { getDefaultRouteForUser } from "@/lib/auth";
import { getCurrentSessionUser } from "@/lib/server-session";

export default async function ChangePasswordPage() {
  const user = await getCurrentSessionUser();
  if (!user) {
    redirect("/login");
  }
  const continueHref = getDefaultRouteForUser({ ...user, must_change_password: false });

  return (
    <div className="page-shell">
      <div className="mx-auto flex min-h-[80vh] max-w-2xl items-center justify-center">
        <div className="brand-panel w-full p-8">
          <div className="mb-6 space-y-3">
            <SchoolLogo />
            <div className="brand-badge">
              {user.must_change_password ? "Primer ingreso" : "Seguridad"}
            </div>
            <h1 className="page-title text-4xl">Actualiza tu contraseña</h1>
            <p className="page-subtitle">
              {user.must_change_password
                ? "Estás usando una contraseña temporal. Te recomendamos actualizarla ahora para proteger tu acceso."
                : "Desde aquí puedes actualizar tu contraseña cuando lo necesites."}
            </p>
            {user.must_change_password ? (
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <Link
                  href={continueHref}
                  className="ghost-button text-sm"
                >
                  Continuar sin cambiarla
                </Link>
              </div>
            ) : null}
          </div>
          <ChangePasswordForm />
        </div>
      </div>
    </div>
  );
}