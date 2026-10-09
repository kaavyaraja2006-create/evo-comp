import type { TokenStatistics as Stats } from "../../types/compiler";

interface Props {
  statistics: Stats;
}

export function TokenStatistics({ statistics }: Props) {
  const cards: { label: string; value: number; emphasis?: boolean }[] = [
    { label: "Total tokens", value: statistics.totalTokens, emphasis: true },
    { label: "Keywords", value: statistics.keywords },
    { label: "Identifiers", value: statistics.identifiers },
    { label: "Literals", value: statistics.literals },
    { label: "Operators", value: statistics.operators },
    { label: "Delimiters", value: statistics.delimiters },
    { label: "Comments", value: statistics.comments },
  ];

  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-text-primary">Token statistics</h3>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {cards.map((c) => (
          <div
            key={c.label}
            className="rounded-md border border-border bg-panel px-3 py-2.5"
          >
            <p className="font-mono text-xl font-semibold text-text-primary">
              {c.value}
            </p>
            <p className="text-[11px] text-text-dim">{c.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
