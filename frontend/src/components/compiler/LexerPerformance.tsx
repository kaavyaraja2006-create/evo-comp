import type { LexerPerformance as Perf } from "../../types/compiler";

interface Props {
  performance: Perf;
}

export function LexerPerformance({ performance }: Props) {
  const items = [
    { label: "Input size", value: `${performance.inputSizeCharacters} chars` },
    { label: "Input lines", value: performance.inputSizeLines },
    { label: "Tokens generated", value: performance.tokensGenerated },
    { label: "Lexing time", value: `${performance.lexingTimeMs} ms` },
  ];

  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-text-primary">Lexer performance</h3>
      <div className="grid grid-cols-2 gap-2">
        {items.map((item) => (
          <div
            key={item.label}
            className="rounded-md border border-border bg-panel px-3 py-2"
          >
            <p className="font-mono text-sm text-text-primary">{item.value}</p>
            <p className="text-[11px] text-text-dim">{item.label}</p>
          </div>
        ))}
      </div>
      <p className="mt-1.5 text-[10px] text-text-dim">
        Measured server-side around the actual scan of this source.
      </p>
    </div>
  );
}
