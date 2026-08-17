"use client";

import { Printer } from "lucide-react";

type StaffPrintLauncherProps = {
  href: string;
  label: string;
  className?: string;
};

export function StaffPrintLauncher({ href, label, className }: StaffPrintLauncherProps) {
  const handleClick = () => {
    const printWindow = window.open(href, "_blank", "noopener,noreferrer");
    if (!printWindow) {
      window.alert("No se pudo abrir la vista de impresión. Revisa el bloqueador de ventanas emergentes.");
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={className ?? "secondary-button inline-flex items-center gap-2 px-4 py-2 text-sm"}
    >
      <Printer className="h-4 w-4" />
      {label}
    </button>
  );
}
