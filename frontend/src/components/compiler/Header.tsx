export function Header() {
  return (
    <header className="flex items-center justify-between border-b border-border bg-panel px-4 py-2.5">
      <div>
        <div className="flex items-baseline gap-2">
          <h1 className="font-mono text-base font-semibold tracking-tight text-text-primary">
            EVO-COMP
          </h1>
          <span className="text-[11px] text-text-dim">
            Interactive Lexical Analysis Laboratory
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="rounded border border-amber-dim bg-amber-dim/10 px-2 py-1 font-mono text-[11px] text-amber">
          Phase 1 / 6
        </span>
      </div>
    </header>
  );
}
