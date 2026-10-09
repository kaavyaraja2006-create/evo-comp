import { useMemo, useState } from "react";
import clsx from "clsx";
import type { Token, TokenCategoryFilter } from "../../types/compiler";
import { TOKEN_CATEGORY_FILTERS } from "../../types/compiler";
import { TOKEN_TYPE_COLOR } from "./tokenTypeStyle";

interface Props {
  tokens: Token[];
  selectedIndex: number | null;
  onSelect: (token: Token) => void;
}

function matchesCategory(token: Token, category: TokenCategoryFilter): boolean {
  switch (category) {
    case "All":
      return true;
    case "Keywords":
      return token.type === "KEYWORD";
    case "Identifiers":
      return token.type === "IDENTIFIER";
    case "Literals":
      return (
        token.type === "INTEGER_LITERAL" ||
        token.type === "FLOAT_LITERAL" ||
        token.type === "STRING_LITERAL" ||
        token.type === "BOOLEAN_LITERAL"
      );
    case "Operators":
      return token.type === "OPERATOR";
    case "Delimiters":
      return token.type === "DELIMITER";
    case "Comments":
      return token.type === "COMMENT";
    case "Errors":
      return false; // lexical errors are shown separately (they aren't tokens)
  }
}

export function TokenTable({ tokens, selectedIndex, onSelect }: Props) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<TokenCategoryFilter>("All");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tokens.filter((t) => {
      if (!matchesCategory(t, category)) return false;
      if (!q) return true;
      return (
        t.type.toLowerCase().includes(q) ||
        t.lexeme.toLowerCase().includes(q) ||
        String(t.value ?? "").toLowerCase().includes(q) ||
        String(t.line).includes(q)
      );
    });
  }, [tokens, search, category]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border-soft px-3 py-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tokens…"
          className="w-44 rounded border border-border bg-panel-raised px-2 py-1 text-xs text-text-primary outline-none placeholder:text-text-dim focus-visible:outline-cyan"
        />
        <div className="flex flex-wrap gap-1">
          {TOKEN_CATEGORY_FILTERS.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={clsx(
                "rounded border px-2 py-1 text-[11px] transition-colors",
                category === c
                  ? "border-cyan-dim bg-cyan-dim/20 text-cyan"
                  : "border-border text-text-secondary hover:bg-panel-hover"
              )}
            >
              {c}
            </button>
          ))}
        </div>
        <span className="ml-auto font-mono text-[11px] text-text-dim">
          {filtered.length} / {tokens.length}
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 bg-panel">
            <tr className="border-b border-border-soft text-text-dim">
              <th className="px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">Token type</th>
              <th className="px-3 py-2 font-medium">Lexeme</th>
              <th className="px-3 py-2 font-medium">Line</th>
              <th className="px-3 py-2 font-medium">Column</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr
                key={t.index}
                onClick={() => onSelect(t)}
                className={clsx(
                  "cursor-pointer border-b border-border-soft/60 font-mono transition-colors hover:bg-panel-hover",
                  selectedIndex === t.index && "bg-cyan-dim/15"
                )}
              >
                <td className="px-3 py-1.5 text-text-dim">{t.index}</td>
                <td className="px-3 py-1.5">
                  <span
                    className={clsx(
                      "rounded border px-1.5 py-0.5 text-[10px]",
                      TOKEN_TYPE_COLOR[t.type]
                    )}
                  >
                    {t.type}
                  </span>
                </td>
                <td className="max-w-[220px] truncate px-3 py-1.5 text-text-primary">
                  {t.type === "EOF" ? "⌀" : t.lexeme}
                </td>
                <td className="px-3 py-1.5 text-text-secondary">{t.line}</td>
                <td className="px-3 py-1.5 text-text-secondary">{t.column}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-text-dim">
                  No tokens match this search/filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
