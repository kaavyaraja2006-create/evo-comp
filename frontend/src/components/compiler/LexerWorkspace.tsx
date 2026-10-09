import { useState } from "react";
import clsx from "clsx";
import type { LexicalCompilation, Token } from "../../types/compiler";
import { CompilationStatus } from "./CompilationStatus";
import { CompilerJourney } from "./CompilerJourney";
import { ErrorPanel } from "./ErrorPanel";
import { TokenStatistics } from "./TokenStatistics";
import { TokenDistribution } from "./TokenDistribution";
import { TokenTable } from "./TokenTable";
import { TokenDetails } from "./TokenDetails";
import { RawTokenJson } from "./RawTokenJson";
import { EventLog } from "./EventLog";
import { LexerPerformance } from "./LexerPerformance";
import { ResearchExplanation } from "./ResearchExplanation";
import type { CompilerEvent } from "../../types/compiler";

interface Props {
  compilation: LexicalCompilation;
  events: CompilerEvent[];
  apiError: string | null;
  selectedToken: Token | null;
  onSelectToken: (token: Token) => void;
  onJumpToLocation: (line: number, column: number) => void;
}

type Tab = "table" | "json";

export function LexerWorkspace({
  compilation,
  events,
  apiError,
  selectedToken,
  onSelectToken,
  onJumpToLocation,
}: Props) {
  const [tab, setTab] = useState<Tab>("table");
  const { result, status } = compilation;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto px-4 py-4">
      <CompilationStatus compilation={compilation} />

      {apiError && (
        <div className="rounded-md border border-red-dim bg-red-dim/10 px-4 py-3 text-xs text-red">
          {apiError}
        </div>
      )}

      {status !== "idle" && <CompilerJourney compilation={compilation} />}

      {result && result.errors.length > 0 && (
        <ErrorPanel errors={result.errors} onJumpTo={onJumpToLocation} />
      )}

      {result && result.success && (
        <>
          <ResearchExplanation />

          <TokenStatistics statistics={result.statistics} />
          <TokenDistribution statistics={result.statistics} />
          <LexerPerformance performance={result.performance} />

          <div className="grid min-h-[420px] grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
            <div className="flex min-h-[420px] flex-col rounded-md border border-border bg-panel">
              <div className="flex border-b border-border-soft">
                {(["table", "json"] as Tab[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={clsx(
                      "px-4 py-2 text-xs font-medium uppercase tracking-wide",
                      tab === t
                        ? "border-b-2 border-cyan text-cyan"
                        : "text-text-dim hover:text-text-secondary"
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="min-h-0 flex-1">
                {tab === "table" ? (
                  <TokenTable
                    tokens={result.tokens}
                    selectedIndex={selectedToken?.index ?? null}
                    onSelect={onSelectToken}
                  />
                ) : (
                  <RawTokenJson tokens={result.tokens} />
                )}
              </div>
            </div>

            <div className="rounded-md border border-border bg-panel">
              <TokenDetails token={selectedToken} />
            </div>
          </div>
        </>
      )}

      <div className="rounded-md border border-border bg-panel">
        <div className="border-b border-border-soft px-3 py-2 text-xs font-medium text-text-secondary">
          Compiler event log
        </div>
        <EventLog events={events} />
      </div>
    </div>
  );
}
