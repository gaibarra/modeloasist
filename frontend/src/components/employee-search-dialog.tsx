"use client";

import { Printer, Search, X } from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";

const CAMPUS_OPTIONS = ["Mérida", "Montejo", "Chetumal", "Valladolid"];

type EmployeeRanking = {
  id: number;
  nombre: string;
  departamento: string;
  campus: string;
  total_days: number;
  late_days: number;
  punctuality_rate: number;
  entrada: string | null;
  weekly_checkins?: WeeklyCheckinRow[];
};

type WeeklyCheckinDay = {
  weekday: number;
  entrada: string | null;
  is_late: boolean | null;
  expected: string | null;
  inferred?: boolean;
};

type WeeklyCheckinRow = {
  week_start: string;
  week_end: string;
  days: WeeklyCheckinDay[];
};

const WEEKDAY_LABELS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

type EmployeeSearchDialogProps = {
  apiBaseUrl: string;
};

const getDepartmentLabel = (department: string) =>
  department.split("/").at(-1)?.trim() || department;

const escapeHtml = (value: string | number | null | undefined) => {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
};

const formatDayMonth = (value: string) =>
  new Date(value).toLocaleDateString("es-MX", { day: "2-digit", month: "short" });

const formatWeekBoundaryDate = (value: string, targetWeekday: number) => {
  const baseDate = new Date(value);
  if (Number.isNaN(baseDate.getTime())) {
    return formatDayMonth(value);
  }

  const jsWeekday = baseDate.getDay();
  const mondayIndexed = (jsWeekday + 6) % 7; // convert to 0 = lunes, 6 = domingo
  const offset = targetWeekday - mondayIndexed;
  const normalized = new Date(baseDate);
  normalized.setDate(baseDate.getDate() + offset);

  return normalized.toLocaleDateString("es-MX", { day: "2-digit", month: "short" });
};

const formatTime = (value: string | null) => (value ? value.slice(0, 5) : "—");

const formatFullDay = (value: string) =>
  new Date(value).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" });

const truncateName = (value: string, maxLength = 28) => {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, Math.max(0, maxLength - 3))}...`;
};

export function EmployeeSearchDialog({ apiBaseUrl }: EmployeeSearchDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [campusFilter, setCampusFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [rankings, setRankings] = useState<EmployeeRanking[]>([]);
  const [weeklyDetailsByEmployee, setWeeklyDetailsByEmployee] = useState<Record<number, WeeklyCheckinRow[]>>({});
  const [expandedEmployeeIds, setExpandedEmployeeIds] = useState<number[]>([]);
  const [detailLoadingEmployeeIds, setDetailLoadingEmployeeIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  const departmentOptions = useMemo(() => {
    const unique = new Set<string>();
    rankings.forEach((row) => unique.add(row.departamento));
    return Array.from(unique).sort((a, b) => a.localeCompare(b));
  }, [rankings]);

  const filteredResults = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    const departmentValue = departmentFilter.trim().toLowerCase();
    return rankings.filter((row) => {
      const matchesSearch = term ? row.nombre.toLowerCase().includes(term) : true;
      const matchesCampus = campusFilter ? row.campus === campusFilter : true;
      const matchesDepartment = departmentValue
        ? row.departamento.toLowerCase() === departmentValue
        : true;
      return matchesSearch && matchesCampus && matchesDepartment;
    });
  }, [rankings, searchTerm, campusFilter, departmentFilter]);

  const reportSummary = useMemo(() => {
    if (filteredResults.length === 0) {
      return {
        count: 0,
        averagePunctuality: "0.0",
        totalLateDays: 0,
        totalRecordedDays: 0,
        bestPerformer: null as EmployeeRanking | null,
      };
    }

    const totalLateDays = filteredResults.reduce((acc, row) => acc + row.late_days, 0);
    const totalRecordedDays = filteredResults.reduce((acc, row) => acc + row.total_days, 0);
    const totalOnTimeDays = filteredResults.reduce(
      (acc, row) => acc + Math.max(row.total_days - row.late_days, 0),
      0,
    );
    const averagePunctuality = totalRecordedDays
      ? ((totalOnTimeDays / totalRecordedDays) * 100).toFixed(1)
      : "0.0";

    const eligibleResults = filteredResults.filter((row) => row.total_days > 0);

    const bestPerformer = eligibleResults.reduce((best: EmployeeRanking | null, candidate) => {
      if (!best) {
        return candidate;
      }

      if (candidate.punctuality_rate > best.punctuality_rate) {
        return candidate;
      }

      if (candidate.punctuality_rate < best.punctuality_rate) {
        return best;
      }

      const candidateOnTime = Math.max(candidate.total_days - candidate.late_days, 0);
      const bestOnTime = Math.max(best.total_days - best.late_days, 0);

      if (candidateOnTime > bestOnTime) {
        return candidate;
      }

      if (candidateOnTime < bestOnTime) {
        return best;
      }

      return candidate.total_days > best.total_days ? candidate : best;
    }, null);

    return {
      count: filteredResults.length,
      averagePunctuality,
      totalLateDays,
      totalRecordedDays,
      bestPerformer,
    };
  }, [filteredResults]);

  const fetchRankings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/analytics/employee-rankings?limit=0`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error("No se pudo obtener la información de colaboradores");
      }
      const payload = (await response.json()) as EmployeeRanking[];
      setRankings(payload);
      setWeeklyDetailsByEmployee({});
      setExpandedEmployeeIds([]);
      setHasLoaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    if (isOpen && !hasLoaded && !loading) {
      fetchRankings();
    }
  }, [isOpen, hasLoaded, loading, fetchRankings]);

  const closeDialog = () => {
    setIsOpen(false);
  };

  const hydrateWeeklyCheckins = useCallback(
    async (employeeIds: number[]) => {
      const uniqueIds = Array.from(new Set(employeeIds.filter((employeeId) => employeeId > 0)));
      if (uniqueIds.length === 0) {
        return {} as Record<number, WeeklyCheckinRow[]>;
      }

      const cached = Object.fromEntries(
        uniqueIds
          .filter((employeeId) => weeklyDetailsByEmployee[employeeId] !== undefined)
          .map((employeeId) => [employeeId, weeklyDetailsByEmployee[employeeId] ?? []]),
      ) as Record<number, WeeklyCheckinRow[]>;
      const missingIds = uniqueIds.filter((employeeId) => weeklyDetailsByEmployee[employeeId] === undefined);

      if (missingIds.length === 0) {
        return cached;
      }

      setDetailLoadingEmployeeIds((current) => Array.from(new Set([...current, ...missingIds])));
      try {
        const query = new URLSearchParams({
          limit: "0",
          includeWeekly: "1",
          weeklyWeeks: "12",
          employeeIds: missingIds.join(","),
        });
        const response = await fetch(`${apiBaseUrl}/analytics/employee-rankings?${query.toString()}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error("No se pudo obtener el detalle semanal de colaboradores");
        }
        const payload = (await response.json()) as EmployeeRanking[];
        const fetched: Record<number, WeeklyCheckinRow[]> = {};
        missingIds.forEach((employeeId) => {
          fetched[employeeId] = [];
        });
        payload.forEach((employee) => {
          fetched[employee.id] = employee.weekly_checkins ?? [];
        });
        setWeeklyDetailsByEmployee((current) => ({ ...current, ...fetched }));
        setRankings((current) =>
          current.map((row) =>
            fetched[row.id] !== undefined ? { ...row, weekly_checkins: fetched[row.id] } : row,
          ),
        );
        return { ...cached, ...fetched };
      } finally {
        setDetailLoadingEmployeeIds((current) => current.filter((employeeId) => !missingIds.includes(employeeId)));
      }
    },
    [apiBaseUrl, weeklyDetailsByEmployee],
  );

  const getWeeklyCheckins = useCallback(
    (employeeId: number) => weeklyDetailsByEmployee[employeeId] ?? [],
    [weeklyDetailsByEmployee],
  );

  const toggleEmployeeDetails = useCallback(
    async (employeeId: number) => {
      if (expandedEmployeeIds.includes(employeeId)) {
        setExpandedEmployeeIds((current) => current.filter((currentId) => currentId !== employeeId));
        return;
      }
      try {
        await hydrateWeeklyCheckins([employeeId]);
        setExpandedEmployeeIds((current) => (current.includes(employeeId) ? current : [...current, employeeId]));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error desconocido");
      }
    },
    [expandedEmployeeIds, hydrateWeeklyCheckins],
  );

  const resetFilters = () => {
    setSearchTerm("");
    setCampusFilter("");
    setDepartmentFilter("");
  };

  const buildReportDocument = (reportRows: EmployeeRanking[]) => {
    const timestamp = new Date().toLocaleString("es-MX", {
      dateStyle: "full",
      timeStyle: "short",
    });

    const activeFilters: Array<{ label: string; value: string }> = [];
    if (searchTerm.trim()) {
      activeFilters.push({ label: "Nombre", value: `Coincidencia: "${searchTerm.trim()}"` });
    }
    if (campusFilter.trim()) {
      activeFilters.push({ label: "Campus", value: campusFilter.trim() });
    }
    if (departmentFilter.trim()) {
      activeFilters.push({ label: "Departamento", value: departmentFilter.trim() });
    }

    const allWeeks = reportRows.flatMap((row) => row.weekly_checkins ?? []);
    let earliestWeekStart: string | null = null;
    let latestWeekEnd: string | null = null;
    allWeeks.forEach((week) => {
      if (week.week_start) {
        if (!earliestWeekStart || new Date(week.week_start) < new Date(earliestWeekStart)) {
          earliestWeekStart = week.week_start;
        }
      }
      if (week.week_end) {
        if (!latestWeekEnd || new Date(week.week_end) > new Date(latestWeekEnd)) {
          latestWeekEnd = week.week_end;
        }
      }
    });

    const periodLabel = earliestWeekStart && latestWeekEnd
      ? `${formatFullDay(earliestWeekStart)} – ${formatFullDay(latestWeekEnd)}`
      : "Periodo no disponible";

    const activeFilterBadges = activeFilters.length
      ? activeFilters
          .map(
            (chip) =>
              `<span class="chip chip--active"><span class="chip__label">${escapeHtml(chip.label)}</span>${escapeHtml(chip.value)}</span>`,
          )
      : ['<span class="chip">Sin filtros específicos</span>'];

    const filterBadges = [
      `<span class="chip chip--range"><span class="chip__label">Periodo</span>${escapeHtml(periodLabel)}</span>`,
      ...activeFilterBadges,
    ].join("\n");

    const chartFilterSummary = activeFilters.length
      ? activeFilters.map((chip) => `${chip.label}: ${chip.value}`).join(" · ")
      : "Sin filtros específicos";

    const rankedEntries = reportRows
      .filter((row) => row.total_days > 0)
      .map((row) => {
        const onTimeDays = Math.max(row.total_days - row.late_days, 0);
        const punctualPercent = row.total_days ? (onTimeDays / row.total_days) * 100 : 0;
        return { row, onTimeDays, punctualPercent };
      })
      .sort((a, b) => {
        if (b.punctualPercent !== a.punctualPercent) {
          return b.punctualPercent - a.punctualPercent;
        }
        if (b.onTimeDays !== a.onTimeDays) {
          return b.onTimeDays - a.onTimeDays;
        }
        if (b.row.total_days !== a.row.total_days) {
          return b.row.total_days - a.row.total_days;
        }
        return a.row.nombre.localeCompare(b.row.nombre);
      })
      .map((entry, index) => ({ ...entry, rank: index + 1 }));

    const namesPerColumn = Math.max(1, Math.ceil(rankedEntries.length / 3));
    const nameColumnsMarkup = Array.from({ length: 3 }, (_, columnIndex) => {
      const start = columnIndex * namesPerColumn;
      const slice = rankedEntries.slice(start, start + namesPerColumn);
      if (slice.length === 0) {
        return `
          <div class="summary-column summary-column--names">
            ${columnIndex === 0 ? '<p class="name-column__empty">Sin colaboradores con registros.</p>' : ""}
          </div>`;
      }

      const items = slice
        .map((entry) => {
          const shortName = truncateName(entry.row.nombre, 28);
          return `
            <li class="name-stack__item">
              <span class="name-stack__rank">#${entry.rank}</span>
              <span class="name-stack__name">${escapeHtml(shortName)}</span>
              <span class="name-stack__value">${entry.punctualPercent.toFixed(1)}%</span>
            </li>`;
        })
        .join("");

      return `
        <div class="summary-column summary-column--names">
          <ul class="name-stack">
            ${items}
          </ul>
        </div>`;
    }).join("");

    const styles = `
      @page {
        size: A4 landscape;
        margin: 18mm;
      }
      :root {
        --ink: #0f172a;
        --muted: #5c6175;
        --surface: #f4f2ff;
        --card: #ffffff;
        --emerald: #0fba81;
        --amber: #f29f05;
        --rose: #f25f5c;
        --slate: #1e1b4b;
        --border: #e7e7f3;
        font-family: "Archivo", "Segoe UI", sans-serif;
        color: var(--ink);
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        padding: 0;
        background: linear-gradient(180deg, #f8f7ff 0%, #f0fbf7 40%, #ffffff 100%);
        color: var(--ink);
        font-family: "Archivo", "Segoe UI", sans-serif;
      }
      .report-shell {
        padding: 32px 40px 48px;
        max-width: 1200px;
        margin: 0 auto;
      }
      h1, h2, h3, h4 {
        margin: 0;
        font-weight: 600;
        color: var(--slate);
      }
      .hero {
        display: flex;
        justify-content: space-between;
        gap: 24px;
        padding: 32px;
        border-radius: 32px;
        background: radial-gradient(circle at 10% 20%, #0fba81 0%, #0d9488 60%, #0f172a 100%);
        color: #fff;
      }
      .hero__meta {
        text-align: right;
        font-size: 14px;
      }
      .filters {
        margin-top: 24px;
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
      }
      .chip {
        background: rgba(15, 186, 129, 0.08);
        border: 1px solid rgba(15, 186, 129, 0.25);
        padding: 10px 16px;
        border-radius: 999px;
        font-size: 13px;
        display: inline-flex;
        gap: 8px;
        align-items: center;
      }
      .chip--active {
        background: rgba(15, 186, 129, 0.18);
        border-color: rgba(15, 186, 129, 0.6);
        color: var(--slate);
        font-weight: 600;
      }
      .chip--range {
        background: #0f172a;
        border-color: #0f172a;
        color: #fff;
        font-weight: 600;
        letter-spacing: 0.04em;
      }
      .chip--range .chip__label {
        color: rgba(255, 255, 255, 0.75);
      }
      .chip__label {
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-size: 11px;
        color: var(--muted);
      }
      .summary-grid {
        margin-top: 28px;
        display: grid;
        grid-template-columns: 1.1fr repeat(3, 1fr);
        gap: 18px;
        align-items: stretch;
      }
      .summary-column {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .summary-column--names {
        background: var(--card);
        border-radius: 24px;
        border: 1px solid var(--border);
        padding: 18px 20px;
        box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
        min-height: 260px;
      }
      .summary-card {
        background: var(--card);
        border-radius: 28px;
        padding: 24px;
        border: 1px solid var(--border);
        box-shadow: 0 25px 60px rgba(15, 23, 42, 0.08);
      }
      .summary-card p {
        margin: 0;
        font-size: 13px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }
      .summary-card h3 {
        font-size: 34px;
        margin-top: 12px;
      }
      .summary-card span {
        font-size: 13px;
        color: var(--muted);
      }
      .name-stack {
        list-style: none;
        padding: 0;
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .name-stack__item {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        font-size: 13px;
        color: var(--slate);
      }
      .name-stack__rank {
        font-weight: 600;
        letter-spacing: 0.08em;
        color: var(--muted);
      }
      .name-stack__name {
        flex: 1;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .name-stack__value {
        font-size: 14px;
        font-weight: 600;
        color: #0f7053;
      }
      .name-column__empty {
        font-size: 13px;
        color: var(--muted);
      }
      .employees {
        margin-top: 32px;
        display: flex;
        flex-direction: column;
        gap: 24px;
        page-break-before: always;
      }
      .trend-section {
        margin-top: 24px;
        padding: 24px 28px 32px;
        border-radius: 28px;
        border: 1px solid var(--border);
        background: #fff;
        box-shadow: 0 15px 40px rgba(15, 23, 42, 0.05);
      }
      .trend-section__header {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .trend-section__title {
        font-size: 20px;
        margin: 4px 0 0;
      }
      .trend-chart__canvas {
        margin-top: 16px;
        border-radius: 24px;
        background: var(--surface);
        padding: 16px;
      }
      .trend-chart__group {
        margin-top: 20px;
      }
      .trend-chart__group-title {
        font-size: 12px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
        margin: 0 0 6px;
      }
      .chart-point-label {
        font-size: 10px;
        font-weight: 600;
        fill: var(--slate);
        paint-order: stroke fill;
        stroke: #ffffff;
        stroke-width: 3px;
      }
      .chart-filter-summary {
        margin-top: 4px;
      }
      .chart-grid {
        stroke: rgba(15, 23, 42, 0.15);
        stroke-dasharray: 4 4;
      }
      .chart-axis {
        stroke: rgba(15, 23, 42, 0.4);
      }
      .chart-label {
        font-size: 10px;
        fill: var(--muted);
        letter-spacing: 0.06em;
      }
      .employee-card {
        border-radius: 24px;
        border: 1px solid var(--border);
        padding: 20px 24px 24px;
        background: #fff;
        box-shadow: 0 20px 50px rgba(15, 23, 42, 0.04);
        page-break-after: always;
        break-inside: avoid;
      }
      .employee-card + .employee-card {
        page-break-before: always;
      }
      .employee-card__title-row {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: flex-start;
      }
      .employee-card__name {
        font-size: 22px;
        margin: 0;
        line-height: 1.1;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        white-space: nowrap;
        color: var(--slate);
      }
      .employee-card__meta-row {
        margin-top: 4px;
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: center;
        font-size: 13px;
        color: var(--muted);
      }
      .employee-card__meta-text {
        font-size: 13px;
        color: var(--muted);
      }
      .page-chip {
        padding: 6px 12px;
        border-radius: 999px;
        border: 1px solid var(--border);
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        white-space: nowrap;
      }
      .page-indicator {
        margin-top: 8px;
        text-align: right;
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }
      .tag {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
        margin: 0;
      }
      .muted {
        color: var(--muted);
        font-size: 13px;
        margin: 4px 0 0;
      }
      .kpi-grid {
        margin-top: 14px;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 10px;
      }
      .kpi {
        background: var(--surface);
        border-radius: 20px;
        padding: 12px 14px;
      }
      .kpi--score {
        background: radial-gradient(circle at 0% 20%, #0fba81 0%, #0a8f67 60%, #0b3a2b 100%);
        color: #fff;
      }
      .kpi__value--score {
        font-size: 32px;
        color: #fff;
      }
      .kpi__label {
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        margin: 0 0 6px;
      }
      .kpi__value {
        font-size: 18px;
        margin: 0;
        color: var(--slate);
      }
      .week-table-wrapper {
        margin-top: 18px;
        border: 1px solid var(--border);
        border-radius: 18px;
        overflow: hidden;
        background: #fff;
      }
      table.week-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 10px;
      }
      table.week-table thead th {
        background: #f5f6fb;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 8px;
        text-align: left;
      }
      table.week-table thead th.week-table__day {
        text-align: center;
      }
      table.week-table tbody td,
      table.week-table tbody th {
        border-top: 1px solid var(--border);
        padding: 6px 8px;
        vertical-align: middle;
      }
      table.week-table tbody tr {
        line-height: 1.2;
      }
      table.week-table tbody td.day-cell {
        text-align: center;
        min-width: 64px;
      }
      .day-cell__expected {
        display: block;
        font-size: 9px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }
      .day-cell__actual {
        display: block;
        font-size: 12px;
        font-weight: 600;
        margin-top: 2px;
      }
      .day-cell__actual.on-time {
        color: #0f7053;
      }
      .day-cell__actual.late {
        color: #b42318;
      }
      .day-cell__actual.neutral {
        color: var(--muted);
      }
      .infer-label {
        font-size: 9px;
        vertical-align: super;
        color: #0f7053;
      }
      .week-table__week {
        width: 120px;
      }
      .week-table__summary {
        font-weight: 600;
        color: var(--slate);
        text-align: right;
        white-space: nowrap;
      }
      .empty-state {
        text-align: center;
        padding: 40px;
        border-radius: 24px;
        border: 1px dashed var(--border);
        color: var(--muted);
      }
      .footnote {
        margin-top: 32px;
        font-size: 11px;
        color: var(--muted);
        text-align: right;
      }
      @media print {
        body {
          background: #fff;
        }
        .report-shell {
          padding: 24px 32px 32px;
        }
        .hero {
          print-color-adjust: exact;
          -webkit-print-color-adjust: exact;
        }
      }
    `;

    const renderWeekBlocks = (weeks?: WeeklyCheckinRow[]) => {
      if (!weeks || weeks.length === 0) {
        return '<p class="muted">Sin registros de checadas en el periodo evaluado.</p>';
      }

      const headerDays = WEEKDAY_LABELS.map(
        (label) => `<th scope="col" class="week-table__day">${escapeHtml(label.slice(0, 3).toUpperCase())}</th>`,
      ).join("");

      const bodyRows = weeks
        .map((week) => {
          const checkedDays = week.days.filter((day) => day.entrada);
          const onTimeDays = checkedDays.filter((day) => day.is_late === false);
          const punctualRate = checkedDays.length
            ? ((onTimeDays.length / checkedDays.length) * 100).toFixed(1)
            : "100.0";
          const punctualCopy = checkedDays.length
            ? `${onTimeDays.length}/${checkedDays.length} días (${punctualRate}%)`
            : "Sin checadas registradas";

          const dayMap = new Map(week.days.map((day) => [day.weekday, day]));
          const dayCells = WEEKDAY_LABELS.map((_, weekdayIndex) => {
            const day = dayMap.get(weekdayIndex);
            const expected = day?.expected ? formatTime(day.expected) : "—";
            const actual = day?.entrada ? formatTime(day.entrada) : "—";
            const cssState = day?.is_late === true ? "late" : day?.is_late === false ? "on-time" : "neutral";
            const inferredMark = day?.inferred ? '<span class="infer-label">*</span>' : "";
            return `
              <td class="day-cell">
                <span class="day-cell__expected">${escapeHtml(expected)}</span>
                <span class="day-cell__actual ${cssState}">${escapeHtml(actual)}${inferredMark}</span>
              </td>`;
          }).join("");

          const mondayLabel = formatWeekBoundaryDate(week.week_end, 0);
          const sundayLabel = formatWeekBoundaryDate(week.week_end, 6);

          return `
            <tr>
              <td>${escapeHtml(mondayLabel)}</td>
              <td>${escapeHtml(sundayLabel)}</td>
              ${dayCells}
              <td class="week-table__summary">${escapeHtml(punctualCopy)}</td>
            </tr>`;
        })
        .join("");

      return `
        <div class="week-table-wrapper">
          <table class="week-table">
            <thead>
              <tr>
                <th scope="col">Semana (inicio)</th>
                <th scope="col">Semana (fin)</th>
                ${headerDays}
                <th scope="col" class="week-table__day">Puntualidad</th>
              </tr>
            </thead>
            <tbody>${bodyRows}</tbody>
          </table>
        </div>`;
    };

    const totalPages = reportRows.length || 1;

    const employeeSections = reportRows
      .map((row, index) => {
        const deptLabel = getDepartmentLabel(row.departamento);
        const totalRecordedDays = row.total_days;
        const onTimeDays = Math.max(totalRecordedDays - row.late_days, 0);
        const punctualPercent = totalRecordedDays
          ? ((onTimeDays / totalRecordedDays) * 100).toFixed(1)
          : null;
        const punctualSummary = totalRecordedDays
          ? `${onTimeDays}/${totalRecordedDays} días puntuales (${punctualPercent}%)`
          : "Sin checadas registradas";
        const punctualDisplay = punctualPercent ? `${punctualPercent}%` : "--";
        const entryPreview = row.entrada ? formatTime(row.entrada) : "—";
        const pageIndicator = `Página ${index + 1} de ${totalPages}`;

        return `
          <article class="employee-card" data-entry-preview="${escapeHtml(entryPreview)}">
            <div class="employee-card__title-row">
              <h4 class="employee-card__name">${escapeHtml(row.nombre)}</h4>
              <span class="page-chip">${escapeHtml(pageIndicator)}</span>
            </div>
            <div class="employee-card__meta-row">
              <p class="tag">Ranking ${index + 1}</p>
              <span class="employee-card__meta-text">${escapeHtml(`${row.campus} · ${deptLabel}`)}</span>
            </div>
            <div class="kpi-grid">
              <div class="kpi kpi--score">
                <p class="kpi__label">Puntualidad</p>
                <p class="kpi__value kpi__value--score">${escapeHtml(punctualDisplay)}</p>
              </div>
              <div class="kpi">
                <p class="kpi__label">Resumen</p>
                <p class="kpi__value">${escapeHtml(punctualSummary)}</p>
              </div>
              <div class="kpi">
                <p class="kpi__label">Checadas</p>
                <p class="kpi__value">${row.total_days}</p>
              </div>
              <div class="kpi">
                <p class="kpi__label">Tardanzas</p>
                <p class="kpi__value">${row.late_days}</p>
              </div>
            </div>
            ${renderWeekBlocks(row.weekly_checkins)}
            <p class="page-indicator">${escapeHtml(pageIndicator)}</p>
          </article>`;
      })
      .join("\n");

    const chartWeeksSet = new Set<string>();
    reportRows.forEach((row) => {
      row.weekly_checkins?.forEach((week) => {
        if (week.week_end) {
          chartWeeksSet.add(week.week_end);
        }
      });
    });

    const chartWeeks = Array.from(chartWeeksSet).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime(),
    );

    const chartWeekLabels = chartWeeks.map((weekKey) => {
      const startLabel = formatWeekBoundaryDate(weekKey, 0);
      const endLabel = formatWeekBoundaryDate(weekKey, 6);
      return `${startLabel} - ${endLabel}`;
    });

    const buildTrendChartSection = () => {
      if (chartWeeks.length === 0) {
        return `
          <section class="trend-section">
            <div class="trend-section__header">
              <p class="tag">Comparativa semanal</p>
              <h3 class="trend-section__title">Evolución de puntualidad</h3>
              <p class="muted">Sin registros suficientes para graficar la tendencia.</p>
            </div>
          </section>`;
      }

      const chartWidth = 900;
      const chartHeight = 380;
      const paddingLeft = 140;
      const paddingRight = 40;
      const paddingTop = 30;
      const paddingBottom = 80;
      const innerWidth = chartWidth - paddingLeft - paddingRight;
      const innerHeight = chartHeight - paddingTop - paddingBottom;
      const xForWeekIndex = (weekIndex: number) => {
        if (chartWeeks.length === 1) {
          return paddingLeft + innerWidth / 2;
        }
        const step = innerWidth / (chartWeeks.length - 1);
        return paddingLeft + weekIndex * step;
      };
      const yForPercent = (percent: number) =>
        paddingTop + innerHeight - (percent / 100) * innerHeight;

      const weekAggregates = chartWeeks.map((weekKey) => {
        const contributingWeeks = reportRows
          .map((row) => row.weekly_checkins?.find((week) => week.week_end === weekKey))
          .filter(Boolean) as WeeklyCheckinRow[];
        if (contributingWeeks.length === 0) {
          return null;
        }
        let punctualDays = 0;
        let totalRecorded = 0;
        contributingWeeks.forEach((week) => {
          week.days.forEach((day) => {
            if (day.entrada) {
              totalRecorded += 1;
              if (day.is_late === false) {
                punctualDays += 1;
              }
            }
          });
        });
        if (totalRecorded === 0) {
          return null;
        }
        return (punctualDays / totalRecorded) * 100;
      });

      const validPoints = weekAggregates.map((percent, weekIndex) =>
        percent === null
          ? null
          : {
              percent,
              weekIndex,
              x: xForWeekIndex(weekIndex),
              y: yForPercent(percent),
            },
      );

      if (!validPoints.some((point) => point !== null)) {
        return `
          <section class="trend-section">
            <div class="trend-section__header">
              <p class="tag">Comparativa semanal</p>
              <h3 class="trend-section__title">Evolución de puntualidad</h3>
              <p class="muted">Sin registros suficientes para graficar la tendencia.</p>
            </div>
          </section>`;
      }

      const axisYTicks = [0, 20, 40, 60, 80, 100];
      const percentGuides = axisYTicks
        .map((tick) => {
          const y = yForPercent(tick);
          return `
            <line x1="${paddingLeft}" y1="${y}" x2="${chartWidth - paddingRight}" y2="${y}" class="chart-grid" />
            <text x="${paddingLeft - 12}" y="${y + 4}" text-anchor="end" class="chart-label">${tick}%</text>`;
        })
        .join("");

      const weekGuides = chartWeekLabels
        .map((label, weekIndex) => {
          const x = xForWeekIndex(weekIndex);
          const labelY = chartHeight - paddingBottom + 28;
          return `
            <line x1="${x}" y1="${paddingTop}" x2="${x}" y2="${chartHeight - paddingBottom}" class="chart-grid" opacity="0.4" />
            <text x="${x}" y="${labelY}" text-anchor="middle" class="chart-label">${escapeHtml(label)}</text>`;
        })
        .join("");

      const pathCommands: string[] = [];
      validPoints.forEach((point) => {
        if (!point) {
          return;
        }
        const prefix = pathCommands.length === 0 ? "M" : "L";
        pathCommands.push(`${prefix} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`);
      });

      const markers = validPoints
        .map((point) =>
          point
            ? `<circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="4" fill="#0FBA81" />`
            : "",
        )
        .join("");

      const markerLabels = validPoints
        .map((point) => {
          if (!point) {
            return "";
          }
          const labelX = Math.min(chartWidth - paddingRight - 4, point.x + 6);
          const labelY = Math.max(paddingTop + 12, point.y - 8);
          return `<text x="${labelX.toFixed(2)}" y="${labelY.toFixed(2)}" class="chart-point-label">${point.percent.toFixed(1)}%</text>`;
        })
        .join("");

      return `
        <section class="trend-section">
          <div class="trend-section__header">
            <p class="tag">Comparativa semanal</p>
            <h3 class="trend-section__title">Evolución de puntualidad consolidada</h3>
            <p class="muted">Porcentaje agregado de puntualidad (todas las checadas registradas por semana)</p>
            <p class="muted chart-filter-summary">Filtros aplicados: ${escapeHtml(chartFilterSummary)}</p>
          </div>
          <div class="trend-chart__group">
            <div class="trend-chart__canvas">
              <svg class="trend-chart__svg" width="${chartWidth}" height="${chartHeight}" viewBox="0 0 ${chartWidth} ${chartHeight}" role="img" aria-label="Tendencia semanal consolidada">
                <g>
                  ${percentGuides}
                  ${weekGuides}
                  <line x1="${paddingLeft}" y1="${paddingTop}" x2="${paddingLeft}" y2="${chartHeight - paddingBottom}" class="chart-axis" />
                  <line x1="${paddingLeft}" y1="${chartHeight - paddingBottom}" x2="${chartWidth - paddingRight}" y2="${chartHeight - paddingBottom}" class="chart-axis" />
                  <path d="${pathCommands.join(" ")}" fill="none" stroke="#0FBA81" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
                  ${markers}
                  ${markerLabels}
                </g>
              </svg>
            </div>
          </div>
        </section>`;
    };

    const trendChartSection = buildTrendChartSection();

    const hasInferredCheckins = reportRows.some((row) =>
      row.weekly_checkins?.some((week) => week.days.some((day) => day.inferred)),
    );

    return `<!DOCTYPE html>
      <html lang="es">
        <head>
          <meta charset="utf-8" />
          <title>Reporte filtrado de puntualidad</title>
          <style>${styles}</style>
        </head>
        <body>
          <main class="report-shell">
            <section class="hero">
              <div>
                <p class="tag">Reporte filtrado</p>
                <h1>Resumen de puntualidad</h1>
                <p class="muted">Colaboradores que cumplen con los filtros seleccionados</p>
              </div>
              <div class="hero__meta">
                <p>Generado: ${escapeHtml(timestamp)}</p>
                <p>Colaboradores incluidos: ${reportSummary.count}</p>
              </div>
            </section>
            <section class="filters">
              ${filterBadges}
            </section>
            <section class="summary-grid">
              <div class="summary-column summary-column--metrics">
                <article class="summary-card">
                  <p>Promedio de puntualidad</p>
                  <h3>${reportSummary.averagePunctuality}%</h3>
                  <span>Checadas puntuales vs. analizadas</span>
                </article>
                <article class="summary-card">
                  <p>Total de tardanzas</p>
                  <h3>${reportSummary.totalLateDays}</h3>
                  <span>Días fuera de tolerancia</span>
                </article>
                <article class="summary-card">
                  <p>Checadas analizadas</p>
                  <h3>${reportSummary.totalRecordedDays}</h3>
                  <span>Registros considerados en el rango</span>
                </article>
              </div>
              ${nameColumnsMarkup}
            </section>
            <section class="employees">
              ${employeeSections || '<p class="empty-state">No se encontraron colaboradores para estos filtros.</p>'}
            </section>
            ${trendChartSection}
            ${
              hasInferredCheckins
                ? '<p class="footnote">* Las horas marcadas con un asterisco fueron inferidas automáticamente para estimar la puntualidad.</p>'
                : ""
            }
          </main>
          <script>
            window.addEventListener('load', () => setTimeout(() => window.print(), 150));
          </script>
        </body>
      </html>`;
  };

  const handleGenerateReport = async () => {
    if (filteredResults.length === 0) {
      window.alert("Aplica un filtro que devuelva al menos un colaborador antes de generar el reporte.");
      return;
    }

    if (typeof window === "undefined") {
      return;
    }

    try {
      const reportWindow = window.open("", "_blank");
      if (!reportWindow) {
        window.alert(
          "No se pudo abrir una nueva ventana para el reporte. Verifica tu bloqueador de ventanas emergentes.",
        );
        return;
      }

      reportWindow.document.open();
      reportWindow.document.write("<html><body style='font-family: sans-serif; padding: 24px;'>Preparando reporte…</body></html>");
      reportWindow.document.close();

      const weeklyDetails = await hydrateWeeklyCheckins(filteredResults.map((row) => row.id));
      const reportRows = filteredResults.map((row) => ({
        ...row,
        weekly_checkins: weeklyDetails[row.id] ?? getWeeklyCheckins(row.id),
      }));

      const reportHtml = buildReportDocument(reportRows);
      reportWindow.document.open();
      reportWindow.document.write(reportHtml);
      reportWindow.document.close();
      reportWindow.focus();
    } catch (err) {
      console.error("Error generando reporte", err);
      window.alert("No pudimos generar el reporte. Intenta de nuevo más tarde.");
    }
  };

  const renderWeeklyTable = (weeks?: WeeklyCheckinRow[]) => {
    if (!weeks || weeks.length === 0) {
      return (
        <p className="text-sm text-(--muted)">
          Sin registros de checadas disponibles para este colaborador.
        </p>
      );
    }
    return (
      <div className="overflow-x-auto">
        <table className="mt-3 w-full text-left text-xs">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-(--muted)">
              <th className="py-1 pr-2">Semana (inicio)</th>
              <th className="py-1 pr-2">Semana (fin)</th>
              {WEEKDAY_LABELS.map((label) => (
                <th key={label} className="py-1 px-1 text-center">
                  {label}
                </th>
              ))}
              <th className="py-1 pl-2 text-center">Puntualidad semanal</th>
            </tr>
          </thead>
          <tbody>
            {weeks.map((week) => {
              const checkedDays = week.days.filter((day) => day.entrada);
              const onTimeDays = checkedDays.filter((day) => day.is_late === false);
              const punctualRate = checkedDays.length
                ? (onTimeDays.length / checkedDays.length) * 100
                : 100;
              const dayMap = new Map(week.days.map((day) => [day.weekday, day]));

              return (
                <tr key={week.week_start} className="border-t border-border">
                  <td className="py-1 pr-2 font-medium text-(--color-brand-strong)">
                    {formatWeekBoundaryDate(week.week_end, 0)}
                  </td>
                  <td className="py-1 pr-2 text-(--muted)">
                    {formatWeekBoundaryDate(week.week_end, 6)}
                  </td>
                  {WEEKDAY_LABELS.map((label, weekdayIndex) => {
                    const day = dayMap.get(weekdayIndex);
                    const expectedColor = day?.inferred
                      ? "text-sky-600"
                      : "text-(--success)";
                    const actualColor = day?.is_late
                      ? "text-red-600"
                      : "text-(--muted)";
                    return (
                      <td key={`${week.week_start}-${label}`} className="py-1 text-center">
                        <div className={`text-[10px] font-semibold uppercase ${expectedColor}`}>
                          {formatTime(day?.expected ?? null)}
                        </div>
                        <div className={`font-semibold ${actualColor}`}>
                          {formatTime(day?.entrada ?? null)}
                        </div>
                      </td>
                    );
                  })}
                  <td className="py-1 pl-2 text-center text-(--muted)">
                    {checkedDays.length === 0
                      ? "Sin checadas"
                      : `${onTimeDays.length}/${checkedDays.length} días (${punctualRate.toFixed(1)}%)`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-2 text-[10px] uppercase tracking-wide text-(--muted)">
          Se muestra la primera checada por día. Las horas en rojo exceden los 10 minutos de tolerancia.
        </p>
      </div>
    );
  };

  return (
    <Fragment>
      <button
        type="button"
        className="secondary-button mt-4 w-full px-4 py-3 text-base"
        onClick={() => setIsOpen(true)}
      >
        Consultar colaboradores
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40 backdrop-blur-sm transition-opacity"
            style={{ background: "linear-gradient(180deg, rgba(227,232,241,0.88) 0%, rgba(214,222,235,0.9) 50%, rgba(244,247,251,0.94) 100%)" }}
            aria-hidden="true"
          />
          <div className="fixed inset-0 z-50 flex items-start justify-center px-3 py-6 sm:px-4 sm:py-10">
            <div className="printable-employee-dialog w-full max-w-5xl overflow-hidden rounded-[28px] border border-white/70 bg-white shadow-[0_30px_80px_rgba(15,23,42,0.18)]">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-5 py-4 sm:flex-nowrap sm:px-6">
                <div>
                  <p className="section-eyebrow">Buscador institucional</p>
                  <h3 className="text-2xl font-semibold text-(--color-brand-strong)">Consulta de colaboradores</h3>
                  <p className="text-sm text-(--muted)">
                    Encuentra cualquier colaborador y revisa su ranking de puntualidad.
                  </p>
                </div>
                <button
                  type="button"
                  className="secondary-button rounded-full p-2 text-(--muted)"
                  onClick={closeDialog}
                  aria-label="Cerrar"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4 border-b border-border px-5 py-4 sm:px-6">
                <div className="grid gap-3 md:grid-cols-3">
                  <label className="flex flex-col text-sm">
                    <span className="mb-1 text-xs font-semibold uppercase tracking-wide text-(--muted)">
                      Nombre
                    </span>
                    <div className="surface-muted flex items-center px-3 py-2 focus-within:border-brand">
                      <Search className="mr-2 h-4 w-4 text-(--muted)" />
                      <input
                        type="text"
                        className="w-full bg-transparent text-base text-foreground outline-none placeholder:text-(--muted)"
                        placeholder="Buscar colaborador"
                        value={searchTerm}
                        onChange={(event) => setSearchTerm(event.target.value)}
                      />
                    </div>
                  </label>

                  <label className="flex flex-col text-sm">
                    <span className="mb-1 text-xs font-semibold uppercase tracking-wide text-(--muted)">
                      Campus
                    </span>
                    <select
                      className="field-input px-3 py-2 text-base"
                      value={campusFilter}
                      onChange={(event) => setCampusFilter(event.target.value)}
                    >
                      <option value="">Todos</option>
                      {CAMPUS_OPTIONS.map((campus) => (
                        <option key={campus} value={campus}>
                          {campus}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col text-sm">
                    <span className="mb-1 text-xs font-semibold uppercase tracking-wide text-(--muted)">
                      Departamento
                    </span>
                    <select
                      className="field-input px-3 py-2 text-base"
                      value={departmentFilter}
                      onChange={(event) => setDepartmentFilter(event.target.value)}
                    >
                      <option value="">Todos</option>
                      {departmentOptions.map((department) => (
                        <option key={department} value={department}>
                          {department}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="flex flex-wrap gap-2 text-sm">
                  <button
                    type="button"
                    className="secondary-button px-3 py-2 text-sm"
                    onClick={resetFilters}
                  >
                    Limpiar filtros
                  </button>
                  <button
                    type="button"
                    className="primary-button px-4 py-2 text-sm"
                    onClick={fetchRankings}
                    disabled={loading}
                  >
                    {loading ? "Actualizando..." : "Actualizar"}
                  </button>
                  <button
                    type="button"
                    className="secondary-button inline-flex items-center gap-2 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={handleGenerateReport}
                    disabled={loading || filteredResults.length === 0}
                  >
                    <Printer className="h-4 w-4" />
                    Reporte filtrado
                  </button>
                </div>
              </div>

              <div className="max-h-[70vh] overflow-y-auto px-3 py-4 leading-normal sm:px-6">
                {error && <p className="alert-error">{error}</p>}

                {!error && (
                  <>
                    <div className="hidden md:block">
                      <div className="overflow-x-auto">
                        <table className="min-w-full text-left text-sm">
                          <thead>
                            <tr className="text-xs uppercase tracking-wide text-(--muted)">
                              <th className="py-2 pr-4">Ranking</th>
                              <th className="py-2 pr-4">Colaborador</th>
                              <th className="py-2 pr-4">Campus</th>
                              <th className="py-2 pr-4">Departamento</th>
                              <th className="py-2 pr-4 text-right">Puntualidad</th>
                              <th className="py-2 text-right">Tardanzas</th>
                              <th className="py-2 pl-4 text-right">Detalle</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredResults.length === 0 && !loading && (
                              <tr>
                                <td colSpan={7} className="py-6 text-center text-sm text-(--muted)">
                                  No encontramos colaboradores con los filtros seleccionados.
                                </td>
                              </tr>
                            )}

                            {loading && (
                              <tr>
                                <td colSpan={7} className="py-6 text-center text-sm text-(--muted)">
                                  Cargando colaboradores...
                                </td>
                              </tr>
                            )}

                            {!loading &&
                              filteredResults.map((row, index) => {
                                const isExpanded = expandedEmployeeIds.includes(row.id);
                                const isDetailLoading = detailLoadingEmployeeIds.includes(row.id);
                                const totalRecordedDays = row.total_days;
                                const onTimeDays = Math.max(totalRecordedDays - row.late_days, 0);
                                const punctualPercent = totalRecordedDays
                                  ? ((onTimeDays / totalRecordedDays) * 100).toFixed(1)
                                  : null;
                                const punctualSummary = totalRecordedDays
                                  ? `${onTimeDays}/${totalRecordedDays} días (${punctualPercent}%)`
                                  : "Sin checadas registradas";
                                return (
                                  <Fragment key={row.id}>
                                    <tr className="border-t border-border text-sm">
                                      <td className="py-2 pr-4 font-semibold text-(--color-brand-strong)">
                                        {index + 1}
                                      </td>
                                      <td className="py-2 pr-4 text-foreground">
                                        <div className="font-semibold">{row.nombre}</div>
                                        <div className="text-xs text-(--muted)">{punctualSummary}</div>
                                      </td>
                                      <td className="py-2 pr-4 text-(--muted)">{row.campus}</td>
                                      <td className="py-2 pr-4 text-(--muted)">{row.departamento}</td>
                                      <td className="py-2 pr-4 text-right font-semibold text-(--color-brand-strong)">
                                        {punctualPercent ? `${punctualPercent}%` : "--"}
                                      </td>
                                      <td className="py-2 text-right text-(--muted)">{row.late_days}</td>
                                      <td className="py-2 pl-4 text-right">
                                        <button
                                          type="button"
                                          className="secondary-button rounded-xl px-3 py-1 text-xs"
                                          onClick={() => void toggleEmployeeDetails(row.id)}
                                        >
                                          {isDetailLoading ? "Cargando..." : isExpanded ? "Ocultar" : "Ver semanas"}
                                        </button>
                                      </td>
                                    </tr>
                                    {isExpanded && (
                                      <tr className="border-b border-border bg-surface-soft text-sm">
                                        <td colSpan={7} className="px-4 py-4">
                                          {renderWeeklyTable(getWeeklyCheckins(row.id))}
                                        </td>
                                      </tr>
                                    )}
                                  </Fragment>
                                );
                              })}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="space-y-4 md:hidden">
                      {filteredResults.length === 0 && !loading && (
                        <div className="surface-muted px-4 py-5 text-center text-sm text-(--muted)">
                          No encontramos colaboradores con los filtros seleccionados.
                        </div>
                      )}
                      {loading && (
                        <div className="surface-muted px-4 py-5 text-center text-sm text-(--muted)">
                          Cargando colaboradores...
                        </div>
                      )}
                      {!loading &&
                        filteredResults.map((row, index) => {
                          const isExpanded = expandedEmployeeIds.includes(row.id);
                          const isDetailLoading = detailLoadingEmployeeIds.includes(row.id);
                          const totalRecordedDays = row.total_days;
                          const onTimeDays = Math.max(totalRecordedDays - row.late_days, 0);
                          const punctualPercent = totalRecordedDays
                            ? ((onTimeDays / totalRecordedDays) * 100).toFixed(1)
                            : null;
                          const punctualSummary = totalRecordedDays
                            ? `${onTimeDays}/${totalRecordedDays} días (${punctualPercent}%)`
                            : "Sin checadas registradas";
                          return (
                            <div key={`mobile-${row.id}`} className="surface-card px-4 py-4">
                              <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                  <p className="text-xs uppercase tracking-wide text-(--muted)">Ranking #{index + 1}</p>
                                  <h4 className="text-lg font-semibold text-(--color-brand-strong)">{row.nombre}</h4>
                                  <p className="text-xs text-(--muted)">{punctualSummary}</p>
                                </div>
                                <div className="text-right text-sm font-semibold text-(--color-brand-strong)">
                                  {punctualPercent ? `${punctualPercent}%` : "--"}
                                  <p className="text-xs font-normal text-(--muted)">
                                    {row.campus} · {row.departamento.split("/").at(-1)}
                                  </p>
                                </div>
                              </div>
                              <div className="surface-muted mt-3 overflow-x-auto px-2 py-2">
                                <button
                                  type="button"
                                  className="secondary-button mb-3 rounded-xl px-3 py-2 text-xs"
                                  onClick={() => void toggleEmployeeDetails(row.id)}
                                >
                                  {isDetailLoading ? "Cargando..." : isExpanded ? "Ocultar detalle semanal" : "Ver detalle semanal"}
                                </button>
                                {isExpanded ? renderWeeklyTable(getWeeklyCheckins(row.id)) : null}
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </Fragment>
  );
}
