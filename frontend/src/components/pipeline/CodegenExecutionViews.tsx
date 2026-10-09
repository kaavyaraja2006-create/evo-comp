import { useState } from "react";
import { Badge, CodeBlock, EmptyState, JsonBlock, Panel, StatGrid, Table } from "./shared";

// --------------------------------------------------------------- Codegen
export function CodegenView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Generate bytecode to see the EvoVM target code." />;
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "source", value: data.source },
          { label: "optimized size", value: `${data.statistics.optimizedSize} instr` },
          { label: "original size", value: `${data.statistics.originalSize} instr` },
          { label: "functions", value: data.statistics.functions },
          { label: "generate time", value: `${data.generateMs} ms` },
        ]}
      />
      <div className="grid gap-3 lg:grid-cols-2">
        <CodeBlock text={data.originalListing} label="Original bytecode" />
        <CodeBlock text={data.listing} label="Optimized bytecode" />
      </div>
      <JsonBlock data={data} label="Full codegen output" />
    </div>
  );
}

// ----------------------------------------------------------------- EvoVM
export function EvmView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Load EvoVM to verify the bytecode before execution." />;
  const vo = data.verification.optimized;
  const vg = data.verification.original;
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "loaded", value: <Badge tone={data.loaded ? "green" : "red"}>{data.loaded ? "yes" : "no"}</Badge> },
          { label: "optimized verified", value: <Badge tone={vo.ok ? "green" : "red"}>{vo.ok ? "OK" : "errors"}</Badge> },
          { label: "original verified", value: <Badge tone={vg.ok ? "green" : "red"}>{vg.ok ? "OK" : "errors"}</Badge> },
          { label: "max call depth", value: data.machine.maxCallDepth },
          { label: "int width", value: `${data.machine.intWidth}-bit` },
        ]}
      />
      <Panel title="Static checks performed">
        <ul className="list-inside list-disc text-[12px] text-text-secondary">
          {data.verification.optimized.checks.map((c: string) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </Panel>
      {(vo.errors.length > 0 || vg.errors.length > 0) && (
        <Panel title="Verification errors">
          <div className="space-y-1 text-[11px] text-red">
            {[...vo.errors, ...vg.errors].map((e: string, i: number) => (
              <p key={i}>{e}</p>
            ))}
          </div>
        </Panel>
      )}
      <Panel title="EvoVM instruction set">
        <Table
          columns={["op", "operand", "stack effect", "description"]}
          rows={data.isa.map((i: any) => [i.op, i.operand, i.stackEffect, i.description])}
        />
      </Panel>
      <JsonBlock data={data} label="Full EvoVM load output" />
    </div>
  );
}

// -------------------------------------------------------------- Execution
export function ExecutionView({ data }: { data: any }) {
  const [step, setStep] = useState(0);
  if (!data) return <EmptyState label="Execute the program on EvoVM to see output and the instruction trace." />;
  const run = data.run;
  const trace = data.trace ?? [];
  const cur = trace[Math.min(step, trace.length - 1)];
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "status", value: <Badge tone={run.status === "HALTED" ? "green" : "red"}>{run.status}</Badge> },
          { label: "instructions executed", value: run.executed },
          { label: "max stack depth", value: run.maxStack },
          { label: "max call depth", value: run.maxCallDepth },
          { label: "wall time", value: `${run.elapsedMs} ms` },
        ]}
      />
      {run.error && (
        <Panel title="Runtime error">
          <p className="text-[12px] text-red">{run.error}</p>
        </Panel>
      )}
      <Panel title="Program output">
        <CodeBlock text={run.output || "(no output)"} />
      </Panel>
      {trace.length > 0 && (
        <Panel title={`Instruction trace (${trace.length}${data.traceTruncated ? "+, truncated" : ""})`}>
          <div className="mb-2 flex items-center gap-2">
            <input
              type="range"
              min={0}
              max={trace.length - 1}
              value={Math.min(step, trace.length - 1)}
              onChange={(e) => setStep(Number(e.target.value))}
              className="flex-1"
            />
            <span className="w-24 text-right font-mono text-[11px] text-text-dim">
              step {step + 1}/{trace.length}
            </span>
          </div>
          {cur && (
            <div className="rounded border border-border-soft bg-void p-2 font-mono text-[12px]">
              <p className="text-cyan">pc {cur.pc} — {cur.text}</p>
              <p className="text-text-dim">function: {cur.function}{cur.irId ? ` (ir#${cur.irId})` : ""}</p>
              <p className="text-text-secondary">stack: [{cur.stack.join(", ")}]</p>
            </div>
          )}
        </Panel>
      )}
      <JsonBlock data={data} label="Full execution output" />
    </div>
  );
}
