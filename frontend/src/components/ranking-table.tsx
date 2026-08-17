interface RankingRow {
  name: string;
  department: string;
  score: number;
  trend: string;
}

interface RankingTableProps {
  title: string;
  rows: RankingRow[];
}

export function RankingTable({ title, rows }: RankingTableProps) {
  return (
    <div className="surface-card p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="section-eyebrow">Ranking institucional</p>
          <h3 className="text-lg font-semibold text-(--color-brand-strong)">{title}</h3>
        </div>
        <span className="status-pill status-success">
          top {rows.length}
        </span>
      </div>
      <div className="space-y-3">
        {rows.map((row, index) => (
          <div
            key={row.name}
            className="surface-subtle flex flex-col gap-3 px-4 py-4 text-sm sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="w-full">
              <p className="font-semibold text-foreground">
                {index + 1}. {row.name}
              </p>
              <p className="text-xs text-(--muted)">{row.department}</p>
            </div>
            <div className="text-sm font-semibold text-(--color-brand-strong) sm:text-right">
              <p>{row.score}%</p>
              <p className="text-xs text-(--color-brand-soft)">{row.trend}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
