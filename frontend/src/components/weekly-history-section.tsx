import { fetchBackendJson } from "@/lib/server-session";

type WeeklyCampusPosition = {
  campus: string;
  position: number;
  position_delta: number;
  total_events: number;
  on_time_events: number;
  late_events: number;
  punctuality_rate: number;
};

type WeeklyHistoryRow = {
  week_start: string;
  week_end: string;
  campuses: WeeklyCampusPosition[];
};

const formatPercent = (value: number | undefined, digits = 1) => `${((value ?? 0) * 100).toFixed(digits)}%`;

const formatTrend = (lateEvents: number | undefined) =>
  lateEvents ? `${lateEvents} llegadas fuera de tolerancia` : "Sin retrasos";

const parseDateOnly = (value: string) => {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month ?? 1) - 1, day ?? 1);
};

const formatWeekRange = (start: string, end: string) => {
  const startDate = parseDateOnly(start);
  const endDate = parseDateOnly(end);
  return `${startDate.toLocaleDateString("es-MX", { day: "2-digit", month: "short" })} - ${endDate.toLocaleDateString(
    "es-MX",
    { day: "2-digit", month: "short" },
  )}`;
};

const formatDelta = (delta: number) => {
  if (delta === 0) return "= sin cambio";
  return `${delta > 0 ? "+" : ""}${delta} posiciones`;
};

async function fetchWeeklyHistory(): Promise<WeeklyHistoryRow[]> {
  return fetchBackendJson<WeeklyHistoryRow[]>("/analytics/weekly-history?weeks=12");
}

async function WeeklyHistorySectionImpl() {
  const weeklyHistory = await fetchWeeklyHistory();

  return (
    <div className="surface-card p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="section-eyebrow">Evolución semanal</p>
          <h2 className="text-2xl font-semibold text-(--color-brand-strong)">Ranking por campus</h2>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-(--muted)">
              <th className="py-2 pr-4">Semana</th>
              <th className="py-2">Posiciones y variación</th>
            </tr>
          </thead>
          <tbody>
            {weeklyHistory.map((row) => (
              <tr key={row.week_start} className="border-t border-[var(--border)]">
                <td className="py-3 pr-4 align-top text-sm font-semibold text-(--color-brand-strong)">
                  {formatWeekRange(row.week_start, row.week_end)}
                </td>
                <td className="py-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    {row.campuses.map((campus) => {
                      const hasRecords = campus.total_events > 0;
                      const punctualityDisplay = hasRecords
                        ? formatPercent(campus.punctuality_rate)
                        : "Sin registros";
                      const detailDisplay = hasRecords
                        ? formatTrend(campus.late_events)
                        : "Sin registros esta semana";
                      return (
                        <div
                          key={`${row.week_start}-${campus.campus}`}
                          className="surface-muted p-3"
                        >
                          <div className="flex items-center justify-between text-sm font-semibold text-(--color-brand-strong)">
                            <span>
                              {campus.position}. {campus.campus}
                            </span>
                            <span>{punctualityDisplay}</span>
                          </div>
                          <div className="mt-1 text-xs text-(--muted)">
                            {formatDelta(campus.position_delta)} · {detailDisplay}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function WeeklyHistorySectionSkeleton() {
  return (
    <div className="surface-card p-6">
      <div className="mb-4">
        <p className="section-eyebrow">Evolución semanal</p>
        <h2 className="text-2xl font-semibold text-(--color-brand-strong)">Ranking por campus</h2>
      </div>
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="surface-muted animate-pulse p-4">
            <div className="h-4 w-36 rounded bg-[var(--border-strong)]" />
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {Array.from({ length: 4 }).map((__, campusIndex) => (
                <div key={campusIndex} className="h-16 rounded-xl bg-[var(--border-strong)]" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export const WeeklyHistorySection = Object.assign(WeeklyHistorySectionImpl, {
  Skeleton: WeeklyHistorySectionSkeleton,
});