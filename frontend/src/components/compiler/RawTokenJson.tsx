import type { Token } from "../../types/compiler";

interface Props {
  tokens: Token[];
}

export function RawTokenJson({ tokens }: Props) {
  const json = JSON.stringify(tokens, null, 2);

  const download = () => {
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "evo-comp-tokens.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border-soft px-3 py-2">
        <span className="text-xs text-text-dim">
          {tokens.length} token object{tokens.length === 1 ? "" : "s"} — raw backend response
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => navigator.clipboard.writeText(json)}
            className="rounded border border-border px-2 py-1 text-[11px] text-text-secondary hover:bg-panel-hover"
          >
            Copy JSON
          </button>
          <button
            onClick={download}
            className="rounded border border-border px-2 py-1 text-[11px] text-text-secondary hover:bg-panel-hover"
          >
            Download JSON
          </button>
        </div>
      </div>
      <pre className="min-h-0 flex-1 overflow-auto px-3 py-2 font-mono text-[11px] leading-relaxed text-text-secondary">
        {json}
      </pre>
    </div>
  );
}
