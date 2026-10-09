import { useState } from "react";
import clsx from "clsx";
import { Badge, CodeBlock, EmptyState, JsonBlock, Panel, StatGrid, Table } from "./shared";

// ------------------------------------------------------------- Evolution
function FitnessChart({ generations }: { generations: any[] }) {
  const vals = generations.map((g) => g.bestFitness ?? 0);
  const avgs = generations.map((g) => g.averageFitness ?? 0);
  const all = [...vals, ...avgs];
  const min = Math.min(0, ...all);
  const max = Math.max(0.01, ...all);
  const w = 560, h = 140, pad = 24;
  const x = (i: number) => pad + (i / Math.max(1, generations.length - 1)) * (w - 2 * pad);
  const y = (v: number) => h - pad - ((v - min) / (max - min)) * (h - 2 * pad);
  const path = (arr: number[]) => arr.map((v, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <line x1={pad} y1={y(0)} x2={w - pad} y2={y(0)} stroke="#232c38" strokeWidth={1} />
      <path d={path(avgs)} fill="none" stroke="#5b6779" strokeWidth={1.5} strokeDasharray="3 3" />
      <path d={path(vals)} fill="none" stroke="#4fc3bd" strokeWidth={2} />
      {vals.map((v, i) => (
        <circle key={i} cx={x(i)} cy={y(v)} r={2.5} fill="#4fc3bd" />
      ))}
    </svg>
  );
}

export function EvolutionView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Run evolution to see generations of candidates." />;
  const cands: Record<string, any> = Object.fromEntries(data.candidates.map((c: any) => [c.id, c]));
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "generations run", value: data.statistics.generationsRun },
          { label: "population", value: data.statistics.populationSize },
          { label: "total candidates", value: data.statistics.totalCandidates },
          { label: "valid", value: data.statistics.validCandidates },
          { label: "rejected", value: data.statistics.rejectedCandidates },
          { label: "cache hits", value: data.statistics.cacheHits },
          { label: "best fitness", value: data.statistics.bestFitness ?? "n/a" },
          { label: "seed", value: data.seed },
        ]}
      />
      <Panel title="Termination">
        <p className="text-[12px] text-text-secondary">{data.termination}</p>
        <p className="mt-1 text-[11px] text-text-dim">{data.reproducibility}</p>
      </Panel>
      <Panel title="Fitness by generation (cyan = best, dashed = population average)">
        <FitnessChart generations={data.generations} />
      </Panel>
      <Panel title="Fitness function">
        <p className="font-mono text-[12px] text-cyan">{data.fitnessFunction.formula}</p>
        <p className="mt-1 text-[11px] text-text-dim">{data.fitnessFunction.hardConstraint}</p>
      </Panel>
      <Panel title="DNA-guided pass weights &amp; how often the Digital Twin had to clean up after each pass">
        <Table
          columns={["pass", "sound", "opportunities", "weight", "times proposed", "proposed in rejected candidate"]}
          rows={data.dnaGuidance.passes.map((p: any) => [
            p.name,
            <Badge key="sound" tone={p.sound ? "green" : "amber"}>{p.sound ? "sound" : "speculative"}</Badge>,
            p.opportunities,
            p.weight.toFixed(2),
            p.timesProposed ?? "—",
            p.timesProposed
              ? (
                <span key="rej" className={p.sound ? "text-text-secondary" : "text-amber"}>
                  {p.timesInRejectedCandidate} / {p.timesProposed}
                  {p.timesProposed > 0 && (
                    <span className="ml-1 text-text-dim">
                      ({((p.timesInRejectedCandidate / p.timesProposed) * 100).toFixed(0)}%)
                    </span>
                  )}
                </span>
              )
              : "—",
          ])}
        />
        <p className="mt-2 text-[11px] text-text-dim">
          "Proposed in rejected candidate" counts how often a genome containing this pass was ultimately rejected by
          the Digital Twin — a real, measured count over this run's actual candidates, not an estimate. Speculative
          passes (amber) are expected to show a materially higher rejection involvement than the sound passes.
        </p>
      </Panel>
      <Panel title={`Hall of fame (${data.hallOfFame.length})`}>
        <Table
          columns={["id", "generation", "genome length", "static size", "dynamic cost", "fitness", "status"]}
          rows={data.hallOfFame.map((id: string) => {
            const c = cands[id];
            return [
              c.id, c.generation, c.genome.length, c.staticSize, c.dynamicCost,
              c.fitness?.toFixed(4) ?? "—",
              <Badge key="status" tone={c.status === "VALID" ? "green" : "red"}>{c.status}</Badge>,
            ];
          })}
        />
      </Panel>
      <JsonBlock data={data} label="Full evolution output (candidates, IR pool, twin pool)" />
    </div>
  );
}

// ------------------------------------------------------- Digital Twin impact
function DigitalTwinImpactPanel({ impact }: { impact: any }) {
  const [showWhatIf, setShowWhatIf] = useState(false);
  const w = impact.whatIf;
  const dangerous = w && w.differsFromActualSelection && !w.actuallyCorrect;
  return (
    <Panel title="Digital Twin impact — rejection rate &amp; the counterfactual: what if it weren't there?">
      <StatGrid
        items={[
          { label: "candidates evaluated", value: impact.candidatesEvaluated },
          { label: "rejected by twin", value: impact.rejectedCount },
          {
            label: "rejection rate",
            value: <Badge tone={impact.rejectionRate > 0 ? "amber" : "green"}>{(impact.rejectionRate * 100).toFixed(1)}%</Badge>,
          },
          { label: "finalists certified", value: impact.finalistsCertified },
          { label: "finalists rejected", value: impact.finalistsRejected },
        ]}
      />
      <p className="mt-2 text-[12px] text-text-secondary">{impact.headline}</p>
      {w && (
        <div className="mt-3">
          <button
            onClick={() => setShowWhatIf((v) => !v)}
            className={clsx(
              "rounded border px-2.5 py-1 text-[11px] font-medium",
              dangerous
                ? "border-red/40 bg-red-dim/20 text-red hover:bg-red-dim/30"
                : "border-border text-text-dim hover:border-cyan hover:text-cyan"
            )}
          >
            {showWhatIf ? "hide" : "show"} what-if: no Digital Twin gating
          </button>
          {showWhatIf && (
            <div
              className={clsx(
                "mt-2 rounded border p-2.5 text-[11px]",
                dangerous ? "border-red/30 bg-red-dim/10" : "border-border-soft bg-panel"
              )}
            >
              <p className="text-text-secondary">{w.explanation}</p>
              <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <div>
                  <p className="text-[10px] uppercase text-text-dim">fitness-only winner</p>
                  <p className="font-mono text-text-primary">{w.wouldSelect}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-text-dim">hypothetical fitness</p>
                  <p className="font-mono text-text-primary">{w.hypotheticalFitness.toFixed(4)}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-text-dim">actually correct?</p>
                  <Badge tone={w.actuallyCorrect ? "green" : "red"}>{w.actuallyCorrect ? "yes" : "NO"}</Badge>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-text-dim">differs from real pick?</p>
                  <Badge tone={w.differsFromActualSelection ? "amber" : "cyan"}>
                    {w.differsFromActualSelection ? "yes" : "no"}
                  </Badge>
                </div>
              </div>
              <p className="mt-2 font-mono text-text-dim">genome: {w.genome.join(" → ") || "(identity)"}</p>
              <p className="mt-1 text-text-dim">function tests: {w.functionTestResult}</p>
              {w.wholeProgramDifferences?.length > 0 && (
                <p className="mt-1 text-red">
                  whole-program diff on <code>{w.wholeProgramDifferences[0].field}</code>: reference=
                  {JSON.stringify(w.wholeProgramDifferences[0].reference)} vs candidate=
                  {JSON.stringify(w.wholeProgramDifferences[0].candidate)}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

// --------------------------------------------- Baseline comparison (item 4)
function BaselineCandidateCard({ c, tone }: { c: any; tone: "cyan" | "amber" }) {
  if (!c.found) {
    return (
      <div className="rounded border border-border-soft bg-void p-2.5 text-[11px] text-text-dim">
        {c.label}: no improving candidate found.
      </div>
    );
  }
  return (
    <div className={clsx("rounded border p-2.5 text-[11px]", tone === "cyan" ? "border-cyan/25 bg-cyan-dim/10" : "border-amber/25 bg-amber-dim/10")}>
      <p className="text-[10px] uppercase tracking-wide text-text-dim">{c.label}</p>
      <p className="mt-1 font-mono text-text-primary">{c.candidateId}</p>
      <p className="mt-1 text-text-secondary">
        {c.dynamicCostReductionPercent}% faster, {c.staticSizeReductionPercent}% smaller, fitness {c.fitness?.toFixed(4)}
      </p>
      <Badge tone={c.actuallyCorrect ? "green" : "red"}>{c.actuallyCorrect ? "behaviorally correct" : "behaviorally WRONG"}</Badge>
      <p className="mt-1 font-mono text-text-dim">{c.genome.join(" → ") || "(identity)"}</p>
    </div>
  );
}

export function BaselineComparisonPanel({
  comparison, status, error, onRun,
}: {
  comparison: any;
  status: "idle" | "running" | "error";
  error: string | null;
  onRun: () => void;
}) {
  return (
    <Panel title="Baseline comparison — what does the Digital Twin actually buy you?">
      <p className="text-[11px] text-text-dim">
        Runs the identical evolutionary search a second time, same seed, with the Digital Twin's correctness gate
        turned off, and reports what a fitness-only search would really have shipped. This re-runs the full search
        (slower than any other action here), so it's on demand rather than automatic.
      </p>
      <div className="mt-2">
        <button
          onClick={onRun}
          disabled={status === "running"}
          className="rounded border border-violet/40 bg-violet/10 px-2.5 py-1 text-[11px] font-medium text-violet hover:bg-violet/20 disabled:opacity-40"
        >
          {status === "running" ? "running second search…" : comparison ? "re-run baseline comparison" : "run baseline comparison"}
        </button>
      </div>
      {status === "error" && error && <p className="mt-2 text-[11px] text-red">{error}</p>}
      {comparison && (
        <div className="mt-3 space-y-3">
          <div
            className={clsx(
              "rounded border p-2.5 text-[12px]",
              comparison.incorrectCandidateWouldShip ? "border-red/30 bg-red-dim/10 text-red" : "border-border-soft bg-panel text-text-secondary"
            )}
          >
            {comparison.headline}
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <BaselineCandidateCard c={comparison.gated} tone="cyan" />
            <BaselineCandidateCard c={comparison.ungated} tone="amber" />
          </div>
          <StatGrid
            items={[
              { label: "seed", value: comparison.seed },
              { label: "population × generations", value: `${comparison.population} × ${comparison.generations}` },
              {
                label: "incorrect candidate would ship?",
                value: <Badge tone={comparison.incorrectCandidateWouldShip ? "red" : "green"}>{comparison.incorrectCandidateWouldShip ? "YES" : "no"}</Badge>,
              },
              { label: "speed gap (pp)", value: comparison.speedGapPercentagePoints ?? "n/a" },
            ]}
          />
          <p className="text-[11px] text-text-dim">{comparison.methodology}</p>
          <JsonBlock data={comparison} label="Full baseline comparison output" />
        </div>
      )}
    </Panel>
  );
}

// ------------------------------------------------------------------ Twin
export function TwinView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Run Digital Twin validation to see the certification matrix." />;
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          {
            label: "selected candidate",
            value: data.selectedCandidateId ? (
              <Badge tone="green">{data.selectedCandidateId}</Badge>
            ) : (
              <Badge tone="amber">fallback: original</Badge>
            ),
          },
          { label: "candidates evaluated", value: data.statistics.candidatesEvaluated },
          { label: "valid", value: data.statistics.valid },
          { label: "rejected", value: data.statistics.rejected },
          { label: "finalists certified", value: data.statistics.finalistsCertified },
          { label: "finalists rejected", value: data.statistics.finalistsRejected },
        ]}
      />
      <Panel title="Selection rule">
        <p className="text-[12px] text-text-secondary">{data.selectionRule}</p>
      </Panel>
      {data.digitalTwinImpact && <DigitalTwinImpactPanel impact={data.digitalTwinImpact} />}
      <Panel title="Finalists (thorough re-validation)">
        <Table
          columns={["candidate", "fitness", "verdict", "function tests"]}
          rows={data.considered.map((c: any) => [
            c.candidateId,
            c.fitness?.toFixed(4) ?? "—",
            <Badge key="verdict" tone={c.verdict === "VALID" ? "green" : "red"}>{c.verdict}</Badge>,
            `${c.passed}/${c.cases}`,
          ])}
        />
      </Panel>
      {data.rejectedExamples.length > 0 && (
        <Panel title="Example rejections (why the Digital Twin caught them)">
          <div className="space-y-2">
            {data.rejectedExamples.map((r: any, i: number) => (
              <div key={i} className="rounded border border-red/20 bg-red-dim/10 p-2 text-[11px]">
                <p className="font-mono text-text-secondary">{r.candidateId}: {r.genome.join(" → ")}</p>
                {r.report.wholeProgram.differences?.length > 0 && (
                  <p className="mt-1 text-red">
                    whole-program diff on <code>{r.report.wholeProgram.differences[0].field}</code>:{" "}
                    reference={JSON.stringify(r.report.wholeProgram.differences[0].reference)} vs
                    candidate={JSON.stringify(r.report.wholeProgram.differences[0].candidate)}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}
      <Panel title="Optimized program (selected)">
        <StatGrid
          items={[
            { label: "genome", value: data.optimized.genome.join(" → ") || "(identity)" },
            { label: "static size", value: `${data.optimized.staticSize} (was ${data.optimized.originalSize})` },
            { label: "dynamic cost", value: `${data.optimized.dynamicCost} (was ${data.optimized.originalDynamicCost})` },
          ]}
        />
        <div className="mt-2">
          <CodeBlock text={data.optimized.irText} label="Optimized IR" />
        </div>
      </Panel>
      <JsonBlock data={data} label="Full Digital Twin output" />
    </div>
  );
}
