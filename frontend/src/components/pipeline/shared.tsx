import { useState, type ReactNode } from "react";
import clsx from "clsx";

export function Panel({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded border border-border bg-panel-raised", className)}>
      {title && (
        <div className="border-b border-border-soft px-3 py-2 text-[11px] font-medium tracking-wide text-text-dim">
          {title}
        </div>
      )}
      <div className="p-3">{children}</div>
    </div>
  );
}

export function StatGrid({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
      {items.map((it) => (
        <div key={it.label} className="rounded border border-border-soft bg-panel px-2.5 py-2">
          <p className="text-[10px] uppercase tracking-wide text-text-dim">{it.label}</p>
          <p className="font-mono text-[13px] text-text-primary">{it.value}</p>
        </div>
      ))}
    </div>
  );
}

export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(text).catch(() => {});
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className="rounded border border-border px-2 py-0.5 text-[10px] text-text-dim hover:border-cyan hover:text-cyan"
    >
      {copied ? "copied" : "copy"}
    </button>
  );
}

export function JsonBlock({ data, label }: { data: unknown; label?: string }) {
  const text = JSON.stringify(data, null, 2);
  return (
    <div className="rounded border border-border-soft bg-void">
      <div className="flex items-center justify-between border-b border-border-soft px-2.5 py-1.5">
        <span className="text-[10px] uppercase tracking-wide text-text-dim">{label ?? "raw JSON"}</span>
        <CopyButton text={text} />
      </div>
      <pre className="max-h-[420px] overflow-auto p-2.5 font-mono text-[11px] leading-relaxed text-text-secondary">
        {text}
      </pre>
    </div>
  );
}

export function CodeBlock({ text, label }: { text: string; label?: string }) {
  return (
    <div className="rounded border border-border-soft bg-void">
      {label && (
        <div className="flex items-center justify-between border-b border-border-soft px-2.5 py-1.5">
          <span className="text-[10px] uppercase tracking-wide text-text-dim">{label}</span>
          <CopyButton text={text} />
        </div>
      )}
      <pre className="max-h-[480px] overflow-auto p-2.5 font-mono text-[11px] leading-relaxed text-text-primary">
        {text}
      </pre>
    </div>
  );
}

export function Bars({
  items,
}: {
  items: { key: string; label: string; value: number; unit?: string }[];
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="space-y-1.5">
      {items.map((it) => (
        <div key={it.key} className="flex items-center gap-2">
          <span className="w-36 shrink-0 truncate text-[11px] text-text-secondary">{it.label}</span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-void">
            <div
              className="h-full rounded bg-cyan/70"
              style={{ width: `${(it.value / max) * 100}%` }}
            />
          </div>
          <span className="w-16 shrink-0 text-right font-mono text-[11px] text-text-dim">
            {it.value}
            {it.unit ? ` ${it.unit}` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

export function Badge({ tone, children }: { tone: "green" | "red" | "amber" | "cyan" | "violet"; children: ReactNode }) {
  const cls = {
    green: "bg-green-dim/40 text-green border-green/30",
    red: "bg-red-dim/40 text-red border-red/30",
    amber: "bg-amber-dim/40 text-amber border-amber/30",
    cyan: "bg-cyan-dim/40 text-cyan border-cyan/30",
    violet: "bg-violet/15 text-violet border-violet/30",
  }[tone];
  return (
    <span className={clsx("rounded border px-1.5 py-0.5 text-[10px] font-medium", cls)}>{children}</span>
  );
}

export function Table({
  columns,
  rows,
  onRowClick,
}: {
  columns: string[];
  rows: ReactNode[][];
  onRowClick?: (i: number) => void;
}) {
  return (
    <div className="overflow-auto rounded border border-border-soft">
      <table className="w-full border-collapse text-left text-[11px]">
        <thead>
          <tr className="border-b border-border-soft bg-panel text-text-dim">
            {columns.map((c) => (
              <th key={c} className="px-2 py-1.5 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              onClick={onRowClick ? () => onRowClick(i) : undefined}
              className={clsx(
                "border-b border-border-soft/60 font-mono",
                onRowClick && "cursor-pointer hover:bg-panel-hover"
              )}
            >
              {r.map((cell, j) => (
                <td key={j} className="px-2 py-1 align-top text-text-secondary">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EmptyState({ label }: { label: string }) {
  return <p className="p-6 text-center text-[12px] text-text-dim">{label}</p>;
}
