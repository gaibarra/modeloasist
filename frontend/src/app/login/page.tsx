import { redirect } from "next/navigation";

import { SchoolLogo } from "@/components/school-logo";
import { LoginForm } from "@/components/login-form";
import { getDefaultRouteForUser } from "@/lib/auth";
import { getCurrentSessionUser } from "@/lib/server-session";

export default async function LoginPage() {
  const user = await getCurrentSessionUser();
  if (user) {
    redirect(getDefaultRouteForUser(user));
  }

  return (
    <div className="page-shell">
      <div className="mx-auto flex min-h-[80vh] max-w-5xl items-center justify-center">
        <div className="brand-panel grid w-full gap-6 p-8 lg:grid-cols-[1.1fr_0.9fr] lg:p-10">
          <section className="relative space-y-5 overflow-hidden">
            <div className="logo-watermark">
              <SchoolLogo withWordmark={false} className="opacity-100" />
            </div>
            <SchoolLogo />
            <div className="brand-badge">Acceso institucional</div>
            <p className="page-subtitle max-w-xl">
              Si es tu primer acceso, puedes cambiar tu contraseña ahora o hacerlo después dentro del sistema.
            </p>
            {/* <div className="surface-muted p-4 text-sm leading-7 text-(--muted)">
              El dashboard global sigue reservado al superadmin. El staff operativo entra a una vista móvil de consultas diarias por departamento.
            </div> */}
          </section>
          <section className="surface-card p-6 sm:p-7">
            <LoginForm />
          </section>
        </div>
      </div>
    </div>
  );
}