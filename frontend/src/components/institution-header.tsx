import { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { SchoolLogo } from "@/components/school-logo";

type InstitutionHeaderProps = {
  eyebrow: string;
  title: string;
  description?: string;
  details?: ReactNode;
  actions?: ReactNode;
  className?: string;
  titleClassName?: string;
  compact?: boolean;
};

export function InstitutionHeader({
  eyebrow,
  title,
  description,
  details,
  actions,
  className,
  titleClassName,
  compact = false,
}: InstitutionHeaderProps) {
  return (
    <header className={cn("brand-panel", compact ? "p-5 sm:p-6" : "p-6 sm:p-8", className)}>
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-4">
          <SchoolLogo className="items-start" />
          <div className="brand-badge">{eyebrow}</div>
          <div className="max-w-3xl space-y-3">
            <h1 className={cn("page-title", compact && "text-3xl sm:text-4xl", titleClassName)}>{title}</h1>
            {details ? <div className="flex flex-wrap gap-2 text-sm">{details}</div> : null}
            {description ? <p className="page-subtitle">{description}</p> : null}
          </div>
        </div>
        {actions ? <div className="flex flex-col items-stretch gap-3 sm:flex-row lg:flex-col">{actions}</div> : null}
      </div>
    </header>
  );
}
