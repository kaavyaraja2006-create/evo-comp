import { useState } from "react";
import { Badge, Bars, EmptyState, JsonBlock, Panel, StatGrid, Table } from "./shared";

// ---------------------------------------------------------------- Parser
export function ParserView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Run the parser to see the syntax tree and parse trace." />;
  const errors = data.errors ?? [];
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "status", value: <Badge tone={data.success ? "green" : "red"}>{data.status}</Badge> },
          { label: "AST nodes", value: data.astNodes ?? "—" },
          { label: "tokens read", value: data.tokensRead },
          { label: "rule invocations", value: data.ruleInvocations },
          { label: "max recursion depth", value: data.maxRecursionDepth },
          { label: "parse time", value: `${data.parseMs} ms` },
          { label: "comments skipped", value: data.commentsSkipped },
          { label: "strategy", value: <span className="text-[10px]">{data.strategy}</span> },
        ]}
      />
      {errors.length > 0 && (
        <Panel title={`Syntax errors (${errors.length})`}>
          <div className="space-y-2">
            {errors.map((e: any, i: number) => (
              <div key={i} className="rounded border border-red/25 bg-red-dim/10 p-2 text-[12px]">
                <p className="text-red">
                  Line {e.line}, column {e.column}: {e.message}
                </p>
                <p className="mt-1 text-[11px] text-text-dim">
                  expected {e.expected}, found <span className="font-mono">{e.found}</span>
                  {e.hint ? ` — ${e.hint}` : ""}
                </p>
              </div>
            ))}
          </div>
        </Panel>
      )}
      {Object.keys(data.ruleCounts ?? {}).length > 0 && (
        <Panel title="Grammar rule invocation counts">
          <Bars
            items={Object.entries(data.ruleCounts)
              .slice(0, 12)
              .map(([k, v]) => ({ key: k, label: k, value: v as number }))}
          />
        </Panel>
      )}
      {data.trace?.length > 0 && (
        <Panel title={`Parse trace (${data.trace.length}${data.traceTruncated ? "+, truncated" : ""})`}>
          <Table
            columns={["#", "rule", "depth", "tokens"]}
            rows={data.trace.slice(0, 200).map((t: any, i: number) => [
              i, t.rule, t.depth, `${t.startToken}–${t.endToken}`,
            ])}
          />
        </Panel>
      )}
      <JsonBlock data={data} label="Full parser output" />
    </div>
  );
}

// ------------------------------------------------------------------- AST
function AstNode({ nodesById, id, depth }: { nodesById: Record<number, any>; id: number; depth: number }) {
  const [open, setOpen] = useState(depth < 3);
  const n = nodesById[id];
  if (!n) return null;
  const hasChildren = n.children.length > 0;
  return (
    <div>
      <div
        className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-0.5 hover:bg-panel-hover"
        style={{ paddingLeft: depth * 14 }}
        onClick={() => hasChildren && setOpen((o) => !o)}
      >
        <span className="w-3 text-center text-[10px] text-text-dim">
          {hasChildren ? (open ? "▾" : "▸") : "·"}
        </span>
        <span className="font-mono text-[12px] text-cyan">{n.type}</span>
        <span className="font-mono text-[11px] text-text-secondary">#{n.id}</span>
        <span className="text-[11px] text-text-dim">
          {n.attributes && Object.keys(n.attributes).length > 0
            ? Object.entries(n.attributes)
                .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                .join(" ")
            : ""}
        </span>
        <span className="ml-auto text-[10px] text-text-dim">
          L{n.loc.line}:{n.loc.column}
        </span>
      </div>
      {open &&
        n.children.map((c: any) => (
          <AstNode key={c.id} nodesById={nodesById} id={c.id} depth={depth + 1} />
        ))}
    </div>
  );
}

export function AstView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Build the AST to see the tree." />;
  const nodesById: Record<number, any> = Object.fromEntries(data.nodes.map((n: any) => [n.id, n]));
  const bad = data.invariants.filter((i: any) => !i.passed);
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "nodes", value: data.statistics.nodeCount },
          { label: "max depth", value: data.statistics.maxDepth },
          { label: "leaves", value: data.statistics.leafCount },
          { label: "build time", value: `${data.buildMs} ms` },
          {
            label: "invariants",
            value: (
              <Badge tone={bad.length === 0 ? "green" : "red"}>
                {data.invariants.length - bad.length}/{data.invariants.length} passed
              </Badge>
            ),
          },
        ]}
      />
      <Panel title="Node types">
        <Bars
          items={Object.entries(data.statistics.byType).map(([k, v]) => ({
            key: k, label: k, value: v as number,
          }))}
        />
      </Panel>
      <Panel title="Syntax tree (click a node with children to expand/collapse)">
        <div className="max-h-[420px] overflow-auto">
          <AstNode nodesById={nodesById} id={data.root} depth={0} />
        </div>
      </Panel>
    </div>
  );
}

// -------------------------------------------------------------- Semantic
export function SemanticView({ data }: { data: any }) {
  if (!data) return <EmptyState label="Run semantic analysis to see the symbol table and diagnostics." />;
  return (
    <div className="space-y-3">
      <StatGrid
        items={[
          { label: "status", value: <Badge tone={data.success ? "green" : "red"}>{data.status}</Badge> },
          { label: "symbols", value: data.statistics.symbolCount },
          { label: "scopes", value: data.statistics.scopeCount },
          { label: "errors", value: data.errorCount },
          { label: "warnings", value: data.warningCount },
          { label: "implicit conversions", value: data.statistics.implicitConversions },
          { label: "analyze time", value: `${data.analyzeMs} ms` },
        ]}
      />
      {data.diagnostics.length > 0 && (
        <Panel title={`Diagnostics (${data.diagnostics.length})`}>
          <div className="space-y-1.5">
            {data.diagnostics.map((d: any, i: number) => (
              <div
                key={i}
                className={`rounded border p-2 text-[12px] ${
                  d.severity === "error" ? "border-red/25 bg-red-dim/10" : "border-amber/25 bg-amber-dim/10"
                }`}
              >
                <span className={d.severity === "error" ? "text-red" : "text-amber"}>
                  [{d.code}] Line {d.line}, column {d.column}:
                </span>{" "}
                <span className="text-text-secondary">{d.message}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}
      <Panel title="Symbol table">
        <Table
          columns={["id", "name", "kind", "type", "scope", "uses"]}
          rows={data.symbols.map((s: any) => [
            s.id, s.name, s.kind, s.type, s.scope, s.useCount,
          ])}
        />
      </Panel>
      <JsonBlock data={data} label="Full semantic output" />
    </div>
  );
}
