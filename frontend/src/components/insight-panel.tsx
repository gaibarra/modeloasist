interface InsightPanelProps {
  persona: "empleado" | "lider";
  message: string;
  bullets: string[];
}

export function InsightPanel({ persona, message, bullets }: InsightPanelProps) {
  const badge = persona === "empleado" ? "Coach IA" : "Rectorado";
  return (
    <section className="surface-card p-5">
      <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-(--color-brand-tint) px-3 py-1 text-xs font-semibold uppercase tracking-wide text-(--color-brand)">
        {badge}
      </div>
      <p className="text-lg leading-8 text-foreground">{message}</p>
      <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-7 text-(--muted)">
        {bullets.map((bullet) => (
          <li key={bullet}>{bullet}</li>
        ))}
      </ul>
    </section>
  );
}
