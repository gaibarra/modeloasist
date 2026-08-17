import Image from "next/image";

import { cn } from "@/lib/utils";

type SchoolLogoProps = {
  className?: string;
  withWordmark?: boolean;
};

export function SchoolLogo({ className, withWordmark = true }: SchoolLogoProps) {
  return (
    <div className={cn("flex items-center gap-4", className)}>
      <div className="surface-subtle flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white p-1.5">
        <Image
          src="/Modelo.jpg"
          alt="Logo de Escuela Modelo"
          width={64}
          height={64}
          className="h-full w-full rounded-full object-cover"
          priority
        />
      </div>
      {withWordmark ? (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-[0.24em]" style={{ color: "var(--color-brand-soft)" }}>
            Escuela Modelo
          </p>
          <p className="text-lg font-semibold sm:text-xl" style={{ color: "var(--color-brand)" }}>
            Asistencia institucional
          </p>
        </div>
      ) : null}
    </div>
  );
}
