import type { TokenStatistics } from "../../types/compiler";

interface Props {
  statistics: TokenStatistics;
}

export function TokenDistribution({ statistics }: Props) {
  const rows: { label: string; value: number; color: string }[] = [
    { label: "Keywords", value: statistics.keywords, color: "bg-amber" },
    { label: "Identifiers", value: statistics.identifiers, color: "bg-cyan" },
    { label: "Literals", value: statistics.literals, color: "bg-violet" },
    { label: "Operators", value: statistics.operators, color: "bg-red" },
    { label: "Delimiters", value: statistics.delimiters, color: "bg-green" },
    { label: "Comments", value: statistics.comments, color: "bg-text-dim" },
  ];

  const max = Math.max(1, ...rows.map((r) => r.value));

  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-text-primary">Token distribution</h3>
      <div className="space-y-1.5 rounded-md border border-border bg-panel px-3 py-3">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center gap-3">
            <span className="w-20 shrink-0 text-[11px] text-text-secondary">{r.label}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel-raised">
              <div
                className={`h-full rounded-full ${r.color}`}
                style={{ width: `${(r.value / max) * 100}%` }}
              />
            </div>
            <span className="w-6 shrink-0 text-right font-mono text-[11px] text-text-dim">
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
