import { Badge, EmptyState, JsonBlock, Panel, StatGrid } from "./shared";

function Metric({ label, m }: { label: string; m: any }) {
  if (!m) return null;
  return (
    <div className="rounded border border-border-soft bg-void px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wide text-text-dim">{label}</p>
      <p className="font-mono text-[13px] text-text-primary">
        {m.original} → {m.optimized}{" "}
        <span className={m.reductionPercent > 0 ? "text-green" : "text-text-dim"}>
          ({m.reductionPercent > 0 ? "-" : ""}{Math.abs(m.reductionPercent)}%)
        </span>
      </p>
    </div>
  );
}

export function ValidationView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Run final validation to compare the optimized and original programs." />;
  const b = data.benchmark;
  const impact = data.report?.digitalTwin?.impact;
  return (
    <div className="space-y-3">
      <Panel>
        <div className="flex items-center gap-3">
          <Badge tone={data.equivalent ? "green" : "red"}>
            {data.equivalent ? "EQUIVALENT" : "NOT EQUIVALENT"}
          </Badge>
          <p className="text-[12px] text-text-secondary">
            {data.equivalent
              ? "The optimized program's behaviour matches the original across every comparison performed."
              : "A real behavioural difference was found — see comparisons below."}
          </p>
        </div>
      </Panel>
      {impact && (
        <Panel title="Digital Twin rejection rate (this run)">
          <StatGrid
            items={[
              { label: "candidates explored", value: impact.candidatesEvaluated },
              { label: "rejected", value: impact.rejectedCount },
              {
                label: "rejection rate",
                value: (
                  <Badge tone={impact.rejectionRate > 0 ? "amber" : "green"}>
                    {(impact.rejectionRate * 100).toFixed(1)}%
                  </Badge>
                ),
              },
              {
                label: "what-if divergence",
                value: impact.whatIf ? (
                  <Badge tone={impact.whatIf.differsFromActualSelection && !impact.whatIf.actuallyCorrect ? "red" : "cyan"}>
                    {impact.whatIf.differsFromActualSelection ? "yes" : "no"}
                  </Badge>
                ) : (
                  "n/a"
                ),
              },
            ]}
          />
          <p className="mt-2 text-[11px] text-text-dim">
            {impact.headline} Full what-if breakdown and per-pass proposal/rejection counts are on the Evolution
            and Digital Twin tabs.
          </p>
        </Panel>
      )}
      <Panel title="Metrics (original → optimized)">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <Metric label="IR instructions" m={data.metrics.irInstructions} />
          <Metric label="IR dynamic cost" m={data.metrics.irDynamicCost} />
          <Metric label="bytecode size" m={data.metrics.bytecodeSize} />
          <Metric label="executed instructions" m={data.metrics.executedInstructions} />
        </div>
      </Panel>
      <Panel title="Benchmark (30 runs, 3 warmup)">
        <StatGrid
          items={[
            { label: "original median", value: `${b.original.medianMs} ms` },
            { label: "optimized median", value: `${b.optimized.medianMs} ms` },
            { label: "speedup", value: b.speedup ? `${b.speedup}×` : "n/a" },
            { label: "noisy", value: <Badge tone={b.noisy ? "amber" : "green"}>{b.noisy ? "yes" : "no"}</Badge> },
          ]}
        />
        <p className="mt-2 text-[11px] text-text-dim">{b.note}</p>
      </Panel>
      {!data.equivalent && (
        <Panel title="Differences found">
          {[data.comparisons.referenceVsOptimizedBytecode, data.comparisons.originalBytecodeVsOptimizedBytecode]
            .filter((c: any) => !c.equivalent)
            .map((c: any, i: number) => (
              <div key={i} className="mb-2 rounded border border-red/25 bg-red-dim/10 p-2 text-[11px]">
                {c.differences.map((d: any, j: number) => (
                  <p key={j} className="text-red">
                    <code>{d.field}</code>: a={JSON.stringify(d.a)} vs b={JSON.stringify(d.b)}
                  </p>
                ))}
              </div>
            ))}
        </Panel>
      )}
      <JsonBlock data={data.report} label="Final compilation report" />
      <JsonBlock data={data} label="Full validation output" />
    </div>
  );
}
