import { Bars, CodeBlock, EmptyState, JsonBlock, Panel, StatGrid } from "./shared";

// -------------------------------------------------------------------- IR
export function IrView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Generate IR to see the three-address code." />;
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "instructions", value: data.statistics.instructions },
          { label: "functions", value: data.statistics.functions },
          { label: "temporaries", value: data.statistics.temporaries },
          { label: "generate time", value: `${data.generateMs} ms` },
        ]}
      />
      <CodeBlock text={data.text} label="IR listing" />
      <JsonBlock data={data} label="Full IR output" />
    </div>
  );
}

// ------------------------------------------------------------------- CFG
function BlockCard({ b }: { b: any }) {
  return (
    <div className="min-w-[220px] rounded border border-border-soft bg-void p-2">
      <div className="mb-1 flex items-center gap-2">
        <span className="font-mono text-[12px] text-cyan">{b.id}</span>
        {b.isLoopHeader && <span className="rounded bg-violet/15 px-1 text-[9px] text-violet">loop header</span>}
        {!b.reachable && <span className="rounded bg-red-dim/40 px-1 text-[9px] text-red">unreachable</span>}
      </div>
      <pre className="whitespace-pre-wrap font-mono text-[10.5px] leading-relaxed text-text-secondary">
        {b.instructions.map((i: any) => i.text).join("\n") || "(empty)"}
      </pre>
      <p className="mt-1 text-[10px] text-text-dim">
        → {b.successors.map((s: any) => `${s.to}(${s.kind})`).join(", ") || "exit"}
      </p>
    </div>
  );
}

export function CfgView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Build the CFG to see basic blocks, loops and dominators." />;
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "blocks", value: data.statistics.blocks },
          { label: "edges", value: data.statistics.edges },
          { label: "branches", value: data.statistics.branches },
          { label: "loops", value: data.statistics.loops },
          { label: "max loop depth", value: data.statistics.maxLoopDepth },
          { label: "cyclomatic complexity", value: data.statistics.cyclomaticComplexity },
          { label: "unreachable blocks", value: data.statistics.unreachableBlocks },
        ]}
      />
      {data.functions.map((f: any) => (
        <Panel key={f.name} title={`function ${f.name} — ${f.statistics.blocks} blocks, ${f.statistics.loops} loop(s)`}>
          <div className="flex flex-wrap gap-2">
            {f.blocks.map((b: any) => (
              <BlockCard key={b.id} b={b} />
            ))}
          </div>
          {f.loops.length > 0 && (
            <p className="mt-2 text-[11px] text-text-dim">
              loops: {f.loops.map((l: any) => `${l.header} (depth ${l.depth}, blocks ${l.blocks.join(",")})`).join("; ")}
            </p>
          )}
        </Panel>
      ))}
      <JsonBlock data={data} label="Full CFG output" />
    </div>
  );
}

// -------------------------------------------------------------------- DNA
export function DnaView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Extract Program DNA to see the structural fingerprint." />;
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "program id", value: data.programId },
          { label: "AST nodes", value: data.features.astNodes },
          { label: "cyclomatic", value: data.features.cyclomatic },
          { label: "opportunity sites", value: data.features.opportunitySites },
        ]}
      />
      <Panel title="Structural profile">
        <Bars items={data.bars.map((b: any) => ({ key: b.key, label: b.label, value: b.value, unit: b.unit }))} />
      </Panel>
      <Panel title="Function profile">
        <p className="text-[12px] text-text-secondary">
          {data.functionProfile.count} function(s), {data.functionProfile.callSites} call site(s)
          {data.functionProfile.recursive.length > 0 && (
            <> — recursive: {data.functionProfile.recursive.join(", ")}</>
          )}
        </p>
      </Panel>
      <Panel title="Optimization opportunities (dry-run pass counts)">
        <Bars
          items={Object.entries(data.optimizationOpportunities).map(([k, v]) => ({
            key: k, label: k, value: v as number,
          }))}
        />
      </Panel>
      <JsonBlock data={data} label="Full Program DNA" />
    </div>
  );
}
