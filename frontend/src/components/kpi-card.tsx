import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  trend?: string;
  icon?: ReactNode;
  className?: string;
}

export function KpiCard({ label, value, trend, icon, className }: KpiCardProps) {
  return (
    <div
      className={cn(
        "surface-card p-5",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-(--muted)">{label}</div>
        {icon}
      </div>
      <div className="mt-3 text-2xl font-semibold text-(--color-brand-strong) sm:text-3xl">{value}</div>
      {trend && <div className="mt-2 text-sm text-(--color-brand-soft)">{trend}</div>}
    </div>
  );
}
