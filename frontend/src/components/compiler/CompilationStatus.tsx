import clsx from "clsx";
import type { LexicalCompilation } from "../../types/compiler";

interface Props {
  compilation: LexicalCompilation;
}

const STAGE_MESSAGES = [
  "Reading source…",
  "Scanning characters…",
  "Recognizing tokens…",
  "Building token stream…",
  "Calculating statistics…",
];

export function CompilationStatus({ compilation }: Props) {
  const { status, result } = compilation;

  if (status === "idle") {
    return (
      <div className="rounded-md border border-border bg-panel px-4 py-3 text-sm text-text-dim">
        Enter or load an EvoLang program, then run{" "}
        <span className="font-mono text-text-secondary">Lexical analyze</span>.
      </div>
    );
  }

  if (status === "running") {
    return (
      <div className="rounded-md border border-amber-dim bg-amber-dim/10 px-4 py-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium text-amber">
          <span className="animate-pulse">◌</span> Lexical analysis running
        </p>
        <ul className="space-y-1 font-mono text-[12px] text-text-secondary">
          {STAGE_MESSAGES.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="rounded-md border border-red-dim bg-red-dim/10 px-4 py-3">
        <p className="text-sm font-medium text-red">✕ Lexical analysis failed</p>
        {result && result.errors.length > 0 && (
          <p className="mt-1 text-xs text-text-secondary">
            {result.errors.length} error{result.errors.length > 1 ? "s" : ""} detected — see
            details below.
          </p>
        )}
      </div>
    );
  }

  return (
    <div
      className={clsx(
        "flex items-center justify-between rounded-md border border-green-dim bg-green-dim/10 px-4 py-3"
      )}
    >
      <p className="text-sm font-medium text-green">✓ Lexical analysis completed</p>
      {result && (
        <p className="font-mono text-xs text-text-secondary">
          {result.statistics.totalTokens} tokens · {result.performance.lexingTimeMs} ms
        </p>
      )}
    </div>
  );
}
