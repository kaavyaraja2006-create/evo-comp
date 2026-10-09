import type { LexicalCompilation } from "../../types/compiler";

interface Props {
  compilation: LexicalCompilation;
}

export function CompilerJourney({ compilation }: Props) {
  const done = compilation.status === "success" || compilation.status === "failed";
  const succeeded = compilation.status === "success";

  const nodeClass = (isDone: boolean) =>
    `rounded-md border px-4 py-2.5 text-center text-xs font-medium ${
      isDone ? "border-green-dim bg-green-dim/10 text-green" : "border-border bg-panel text-text-dim"
    }`;

  return (
    <div className="flex items-center gap-2 font-mono text-xs">
      <div className={nodeClass(true)}>Source code ✓</div>
      <span className="text-text-dim">→</span>
      <div className={nodeClass(done)}>Lexer {done ? (succeeded ? "✓" : "✕") : ""}</div>
      <span className="text-text-dim">→</span>
      <div className={nodeClass(succeeded)}>
        Token stream{" "}
        {succeeded && compilation.result
          ? `— ${compilation.result.statistics.totalTokens} tokens`
          : ""}
      </div>
    </div>
  );
}
