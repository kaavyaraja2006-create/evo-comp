import type { Token } from "../../types/compiler";
import { TOKEN_TYPE_COLOR } from "./tokenTypeStyle";
import clsx from "clsx";

interface Props {
  token: Token | null;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-text-dim">{label}</p>
      <p className="font-mono text-sm text-text-primary">{value}</p>
    </div>
  );
}

export function TokenDetails({ token }: Props) {
  if (!token) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center text-xs text-text-dim">
        Select a token from the table to inspect its details.
      </div>
    );
  }

  return (
    <div className="space-y-3 px-4 py-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-text-primary">
          Token #{token.index}
        </h3>
        <span
          className={clsx(
            "rounded border px-1.5 py-0.5 text-[10px]",
            TOKEN_TYPE_COLOR[token.type]
          )}
        >
          {token.type}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Lexeme" value={token.lexeme || "⌀"} />
        <Field label="Value" value={String(token.value ?? "null")} />
        <Field label="Line" value={token.line} />
        <Field label="Column" value={token.column} />
        <Field label="Character range" value={`${token.start} – ${token.end}`} />
      </div>
    </div>
  );
}
