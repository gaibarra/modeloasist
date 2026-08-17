"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";

type DataRefreshPanelProps = {
  apiBaseUrl: string;
};

type Status = "idle" | "loading" | "success" | "error";

type ControlState = {
  status: Status;
  message: string;
};

const INITIAL_STATE: ControlState = { status: "idle", message: "" };

export function DataRefreshPanel({ apiBaseUrl }: DataRefreshPanelProps) {
  const [weeklyState, setWeeklyState] = useState<ControlState>(INITIAL_STATE);
  const [dashboardState, setDashboardState] = useState<ControlState>(INITIAL_STATE);

  const runRefresh = async (
    path: string,
    setState: (updater: ControlState) => void,
    successMessage: string,
  ) => {
    setState({ status: "loading", message: "Actualizando..." });
    try {
      const response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }
      setState({ status: "success", message: successMessage });
    } catch (error) {
      setState({ status: "error", message: error instanceof Error ? error.message : "Error desconocido" });
    }
  };

  const statusStyles: Record<Status, string> = {
    idle: "text-(--muted)",
    loading: "text-(--warning)",
    success: "text-(--success)",
    error: "text-red-600",
  };

  const renderButton = (
    label: string,
    description: string,
    state: ControlState,
    onClick: () => void,
  ) => (
    <div className="surface-muted flex flex-col gap-2 p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-(--color-brand-strong)">{label}</p>
          <p className="text-xs text-(--muted)">{description}</p>
        </div>
        <button
          type="button"
          className="secondary-button inline-flex items-center gap-2 px-4 py-1.5 text-sm"
          onClick={onClick}
          disabled={state.status === "loading"}
        >
          <RefreshCw className={`h-4 w-4 ${state.status === "loading" ? "animate-spin" : ""}`} />
          {state.status === "loading" ? "Procesando" : "Ejecutar"}
        </button>
      </div>
      {state.message && (
        <p className={`text-xs font-medium ${statusStyles[state.status]}`}>{state.message}</p>
      )}
    </div>
  );

  return (
    <div className="surface-card space-y-3 p-4">
      <p className="section-eyebrow">Actualizaciones manuales</p>
      <h3 className="text-lg font-semibold text-(--color-brand-strong)">Disparadores de datos</h3>
      {renderButton(
        "Recalcular histórico semanal",
        "Ejecuta /analytics/weekly-history?weeks=12 para poblar métricas",
        weeklyState,
        () => runRefresh("/analytics/weekly-history?weeks=12&refresh=1", setWeeklyState, "Histórico actualizado"),
      )}
      {renderButton(
        "Recalcular snapshot global",
        "Ejecuta /analytics/dashboard y actualiza inferencias",
        dashboardState,
        () => runRefresh("/analytics/dashboard?refresh=1", setDashboardState, "Dashboard actualizado"),
      )}
    </div>
  );
}
