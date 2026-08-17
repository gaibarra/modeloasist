import { ChangePasswordLink } from "@/components/change-password-link";
import { LogoutButton } from "@/components/logout-button";
import { InstitutionHeader } from "@/components/institution-header";
import { fetchOwnAttendanceRecord, requireEmployeeUser } from "@/lib/server-session";

const WEEKDAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" });

const formatTime = (value: string | null) => (value ? value.slice(0, 5) : "—");

export default async function MyAttendancePage() {
  const user = await requireEmployeeUser();
  const record = await fetchOwnAttendanceRecord();

  return (
    <div className="page-shell text-foreground">
      <div className="page-container max-w-6xl">
        <InstitutionHeader
          eyebrow="Récord personal"
          title={`Hola, ${user.nombre}`}
          description="Consulta tus asistencias recientes, tu puntualidad acumulada y el detalle semanal de tus entradas."
          actions={<><ChangePasswordLink /><LogoutButton /></>}
        />
        <section className="surface-card p-6">
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <div className="surface-muted p-4">
              <p className="section-eyebrow">Puntualidad</p>
              <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{formatPercent(record.summary.punctuality_rate)}</p>
            </div>
            <div className="surface-muted p-4">
              <p className="section-eyebrow">Días registrados</p>
              <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{record.summary.total_days}</p>
            </div>
            <div className="surface-muted p-4">
              <p className="section-eyebrow">Horario esperado</p>
              <p className="mt-2 text-2xl font-semibold text-(--color-brand-strong)">{formatTime(record.summary.expected_entry_time)}</p>
            </div>
          </div>
        </section>

        <main className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <section className="surface-card p-6">
            <div className="mb-4">
              <p className="section-eyebrow">Semanas recientes</p>
              <h2 className="text-2xl font-semibold text-(--color-brand-strong)">Detalle de asistencia</h2>
            </div>
            <div className="space-y-4">
              {record.weekly_checkins.length === 0 ? (
                <div className="surface-muted border-dashed p-6 text-sm text-(--muted)">
                  No hay semanas registradas todavía.
                </div>
              ) : (
                record.weekly_checkins.map((week) => (
                  <article key={week.week_start} className="surface-muted p-4">
                    <div className="mb-3 flex items-center justify-between gap-4">
                      <h3 className="text-sm font-semibold text-(--color-brand-strong)">
                        {formatDate(week.week_start)} - {formatDate(week.week_end)}
                      </h3>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      {week.days.map((day) => {
                        const statusClass = day.is_late === null ? "status-neutral" : day.is_late ? "status-danger" : "status-success";
                        return (
                        <div key={`${week.week_start}-${day.weekday}`} className="surface-card rounded-2xl p-3 shadow-none">
                          <p className="section-eyebrow">{WEEKDAY_LABELS[day.weekday] ?? `Día ${day.weekday + 1}`}</p>
                          <p className="mt-2 text-lg font-semibold text-(--color-brand-strong)">{formatTime(day.entrada)}</p>
                          <p className="mt-1 text-xs text-(--muted)">Esperado: {formatTime(day.expected)}</p>
                          <p className={`status-pill mt-2 ${statusClass}`}>
                            {day.is_late === null ? "Sin registro" : day.is_late ? "Fuera de tolerancia" : "A tiempo"}
                          </p>
                        </div>
                      )})}
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>

          <aside className="space-y-6">
            <section className="surface-card p-6">
              <div className="mb-4">
                <p className="section-eyebrow">Eventos recientes</p>
                <h2 className="text-xl font-semibold text-(--color-brand-strong)">Últimos registros</h2>
              </div>
              <ul className="space-y-3">
                {record.recent_events.map((event) => (
                  <li key={event.id} className="surface-muted p-4 text-sm">
                    <div className="flex items-center justify-between gap-4">
                      <span className="font-semibold text-foreground">{formatDate(event.fecha)}</span>
                      <span className="text-(--muted)">{formatTime(event.tiempo)}</span>
                    </div>
                    <p className="mt-2 text-xs text-(--muted)">{event.device_name ?? "Sin lector"} · {event.device_serial ?? "Sin serie"}</p>
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        </main>
      </div>
    </div>
  );
}