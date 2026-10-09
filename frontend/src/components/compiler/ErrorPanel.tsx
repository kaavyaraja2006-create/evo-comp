import type { LexicalError } from "../../types/compiler";

interface Props {
  errors: LexicalError[];
  onJumpTo?: (line: number, column: number) => void;
}

export function ErrorPanel({ errors, onJumpTo }: Props) {
  if (errors.length === 0) return null;

  return (
    <div className="rounded-md border border-red-dim bg-panel">
      <div className="border-b border-red-dim/50 px-4 py-2">
        <h3 className="text-sm font-medium text-red">Lexical errors</h3>
      </div>
      <ul className="divide-y divide-border-soft">
        {errors.map((err, i) => (
          <li
            key={i}
            className="cursor-pointer px-4 py-2.5 text-xs hover:bg-panel-hover"
            onClick={() => onJumpTo?.(err.line, err.column)}
          >
            <div className="flex items-center gap-3 font-mono text-text-secondary">
              <span>Line {err.line}</span>
              <span>Column {err.column}</span>
              {err.character && (
                <span className="rounded bg-red-dim/30 px-1.5 py-0.5 text-red">
                  '{err.character}'
                </span>
              )}
            </div>
            <p className="mt-1 text-text-primary">{err.message}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
