import { Suspense } from "react";
import Link from "next/link";
import { ArrowUpRight, Sparkles, Trophy } from "lucide-react";

import { ChangePasswordLink } from "@/components/change-password-link";
import { DataRefreshPanel } from "@/components/data-refresh-panel";
import { EmployeeSearchDialogLazy } from "@/components/employee-search-dialog-lazy";
import { InsightPanel } from "@/components/insight-panel";
import { InstitutionHeader } from "@/components/institution-header";
import { KpiCard } from "@/components/kpi-card";
import { LogoutButton } from "@/components/logout-button";
import { RankingTable } from "@/components/ranking-table";
import { WeeklyHistorySection } from "@/components/weekly-history-section";
import { fetchBackendJson, requireAdminUser } from "@/lib/server-session";

type GlobalMetrics = {
  window_start: string;
  window_end: string;
  total_events: number;
  on_time_events: number;
  late_events: number;
  punctuality_rate: number;
  active_employees: number;
};

type CampusMetric = {
  campus: string;
  total_events: number;
  active_employees: number;
  on_time_events: number;
  late_events: number;
  punctuality_rate: number;
};

type WeeklyCheckinDay = {
  weekday: number;
  entrada: string | null;
  is_late: boolean | null;
  expected?: string | null;
  inferred?: boolean;
};

type WeeklyCheckinRow = {
  week_start: string;
  week_end: string;
  days: WeeklyCheckinDay[];
};

type EmployeeRanking = {
  id: number;
  nombre: string;
  departamento: string;
  campus: string;
  total_days: number;
  late_days: number;
  punctuality_rate: number;
  entrada?: string | null;
  weekly_checkins?: WeeklyCheckinRow[];
};

type TimelineEntry = {
  title: string;
  detail: string;
  time: string;
};

type DashboardResponse = {
  global_metrics: GlobalMetrics;
  campus_metrics: CampusMetric[];
  top_employees: EmployeeRanking[];
  timeline: TimelineEntry[];
};

const CLIENT_API_BASE_URL = process.env.NEXT_PUBLIC_CLIENT_API_BASE_URL ?? "/api";

async function fetchDashboard(): Promise<DashboardResponse> {
  return fetchBackendJson<DashboardResponse>("/analytics/dashboard");
}

const formatPercent = (value: number | undefined, digits = 1) => `${((value ?? 0) * 100).toFixed(digits)}%`;

const numberFormatter = new Intl.NumberFormat("es-MX");

const formatNumber = (value: number | undefined) => numberFormatter.format(value ?? 0);

const percentOfTotal = (part: number | undefined, total: number | undefined) =>
  formatPercent(total && total > 0 ? (part ?? 0) / total : 0);

const formatTrend = (lateEvents: number | undefined) =>
  lateEvents ? `${lateEvents} llegadas fuera de tolerancia` : "Sin retrasos";

export default async function Home() {
  await requireAdminUser();
  const dashboard = await fetchDashboard();
  const { global_metrics: globalMetrics, campus_metrics: campusMetrics, top_employees: topEmployees, timeline } =
    dashboard;

  const kpis = [
    {
      label: "Puntualidad global",
      value: formatPercent(globalMetrics.punctuality_rate),
      trend: `${formatNumber(globalMetrics.on_time_events)} registros puntuales`,
      icon: <ArrowUpRight className="h-4 w-4 text-(--color-brand)" />,
    },
    {
      label: "Registros puntuales",
      value: formatNumber(globalMetrics.on_time_events),
      trend: `${percentOfTotal(globalMetrics.on_time_events, globalMetrics.total_events)} del total`,
      icon: <Sparkles className="h-4 w-4 text-(--color-brand-soft)" />,
    },
    {
      label: "Llegadas fuera de tolerancia",
      value: formatNumber(globalMetrics.late_events),
      trend: `${percentOfTotal(globalMetrics.late_events, globalMetrics.total_events)} del total`,
      icon: <Trophy className="h-4 w-4 text-(--warning)" />,
    },
  ];

  const rankingRows = topEmployees.map((employee) => ({
    name: employee.nombre,
    department: `${employee.campus} · ${employee.departamento.split("/").at(-1) ?? employee.departamento}`,
    score: Math.round(employee.punctuality_rate * 100),
    trend: formatTrend(employee.late_days),
  }));

  const campusLeader = [...campusMetrics].sort(
    (a, b) => b.punctuality_rate - a.punctuality_rate,
  )[0];
  const campusLagging = [...campusMetrics].sort((a, b) => a.punctuality_rate - b.punctuality_rate)[0];
  const highlightedEmployee = topEmployees[0];

  const employeeMessage = highlightedEmployee
    ? `Hola ${highlightedEmployee.nombre.split(" ")[0]}, mantienes ${formatPercent(
        highlightedEmployee.punctuality_rate,
      )} de puntualidad en ${highlightedEmployee.campus}.`
    : "Aún no hay registros suficientes para personalizar tu coaching.";

  const employeeBullets = highlightedEmployee
    ? [
        `${highlightedEmployee.total_days} registros analizados con ${formatTrend(
          highlightedEmployee.late_days,
        ).toLowerCase()}.`,
        `Tu campus promedia ${formatPercent(
          campusMetrics.find((metric) => metric.campus === highlightedEmployee.campus)?.punctuality_rate ?? 0,
        )} de puntualidad.`,
        "Comparte tu progreso con tu directora para mantener la racha.",
      ]
    : ["Conecta tus lectores para comenzar a recibir recomendaciones."];

  const leaderMessage = campusLeader
    ? `${campusLeader.campus} lidera con ${formatPercent(campusLeader.punctuality_rate)} de puntualidad.`
    : "Sin datos por campus disponibles.";

  const leaderBullets = campusLeader
    ? [
        `${campusLeader.active_employees} colaboradores activos y ${formatNumber(
          campusLeader.late_events,
        )} alertas en el periodo.`,
        campusLagging
          ? `${campusLagging.campus} requiere refuerzos: ${formatPercent(
              campusLagging.punctuality_rate,
            )} de puntualidad.`
          : "",
        "Revisa las tendencias por hora para programar acompañamientos.",
      ].filter(Boolean)
    : ["Activa tus campus para ver su desempeño en tiempo real."];

  return (
    <div className="page-shell text-foreground">
      <div className="page-container max-w-6xl gap-8">
        <InstitutionHeader
          eyebrow="Mejora continua"
          title="Tablero de puntualidad"
          description="Datos reales de Escuela Modelo para Mérida, Montejo, Chetumal y Valladolid, con una vista sobria y clara para dar seguimiento institucional." 
          actions={<><ChangePasswordLink /><Link href="/staff/admin" className="secondary-button">Gestionar staff</Link><LogoutButton /></>}
        />
        <section className="surface-card p-6 sm:p-8">
          <div className="mt-6 -mx-1 flex snap-x snap-mandatory gap-4 overflow-x-auto pb-3 pl-1 pr-2 md:mx-0 md:grid md:grid-cols-3 md:gap-4 md:overflow-visible md:pb-0 md:pl-0 md:pr-0 md:snap-none">
            {kpis.map((kpi) => (
              <KpiCard
                key={kpi.label}
                {...kpi}
                className="min-w-[230px] shrink-0 snap-start md:min-w-0"
              />
            ))}
          </div>
          <div className="mt-6 -mx-1 flex snap-x snap-mandatory gap-4 overflow-x-auto pb-3 pl-1 pr-2 md:mx-0 md:grid md:grid-cols-2 md:gap-4 md:overflow-visible md:pb-0 md:pl-0 md:pr-0 md:snap-none lg:grid-cols-4">
            {campusMetrics.map((campus) => (
              <KpiCard
                key={campus.campus}
                label={`Puntualidad ${campus.campus}`}
                value={formatPercent(campus.punctuality_rate)}
                trend={`${formatNumber(campus.on_time_events)} puntuales · ${formatNumber(
                  campus.late_events,
                )} fuera de tolerancia`}
                className="min-w-[230px] shrink-0 snap-start md:min-w-0"
              />
            ))}
          </div>
        </section>

        <main className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <section className="space-y-6">
            <div className="surface-card p-6">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="section-eyebrow">
                    Línea de tiempo
                  </p>
                  <h2 className="text-2xl font-semibold text-(--color-brand-strong)">
                    Operación diaria
                  </h2>
                </div>
                <button className="secondary-button">
                  Exportar
                </button>
              </div>
              <ul className="space-y-4">
                {timeline.map((item, index) => (
                  <li key={`${item.title}-${index}`} className="flex gap-4">
                    <div className="text-xs font-semibold uppercase tracking-wide text-(--brand-soft)">
                      {item.time}
                    </div>
                    <div className="surface-muted flex-1 p-4">
                      <p className="text-base font-semibold text-(--color-brand-strong)">
                        {item.title}
                      </p>
                      <p className="text-sm text-(--muted)">{item.detail}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <Suspense fallback={<WeeklyHistorySection.Skeleton />}>
              <WeeklyHistorySection />
            </Suspense>

            <InsightPanel persona="empleado" message={employeeMessage} bullets={employeeBullets} />
          </section>

          <aside className="space-y-6">
            <DataRefreshPanel apiBaseUrl={CLIENT_API_BASE_URL} />
            <RankingTable title="Top colaboradores campus" rows={rankingRows} />
            <EmployeeSearchDialogLazy apiBaseUrl={CLIENT_API_BASE_URL} />
            <InsightPanel persona="lider" message={leaderMessage} bullets={leaderBullets} />
          </aside>
        </main>
      </div>
    </div>
  );
}
