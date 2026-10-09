export function ResearchExplanation() {
  return (
    <div className="rounded-md border border-border bg-panel px-4 py-3">
      <p className="mb-1 text-[11px] font-medium text-text-secondary">What happened?</p>
      <p className="text-[12px] leading-relaxed text-text-dim">
        The lexical analyzer scanned the EvoLang source character-by-character and
        grouped valid character sequences into tokens. Each token records its lexical
        category and exact source position, forming the token stream a future parser
        phase would consume.
      </p>
    </div>
  );
}
