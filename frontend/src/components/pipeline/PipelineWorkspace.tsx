import type { JSX } from "react";
import { usePipeline } from "../../hooks/usePipeline";
import type { StageName } from "../../types/pipeline";
import { STAGE_LABELS } from "./stageMeta";
import { ParserView, AstView, SemanticView } from "./ParserAstSemanticViews";
import { IrView, CfgView, DnaView } from "./IrCfgDnaViews";
import { EvolutionView, TwinView, BaselineComparisonPanel } from "./EvolutionTwinViews";
import { CodegenView, EvmView, ExecutionView } from "./CodegenExecutionViews";
import { ValidationView } from "./ValidationView";
import { Badge } from "./shared";

const VIEWS: Partial<Record<StageName, (props: { data: any }) => JSX.Element>> = {
  parser: ParserView, ast: AstView, semantic: SemanticView,
  ir: IrView, cfg: CfgView, dna: DnaView,
  evolution: EvolutionView, twin: TwinView,
  codegen: CodegenView, evovm: EvmView, execution: ExecutionView,
  validation: ValidationView,
};

interface Props {
  pipeline: ReturnType<typeof usePipeline>;
}

export function PipelineWorkspace({ pipeline }: Props) {
  const { state, runOneStage, runAll, runBaselineComparison } = pipeline;
  const stage = state.selectedStage;
  const st = state.stages[stage];
  const View = VIEWS[stage];
  const busy = state.mode !== "idle";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-border-soft bg-panel px-3 py-2">
        <div className="flex items-center gap-2">
          <h2 className="font-mono text-[13px] text-text-primary">{STAGE_LABELS[stage]}</h2>
          {st.status !== "not_started" && (
            <Badge tone={st.status === "completed" ? "green" : "red"}>{st.status}</Badge>
          )}
          {st.durationMs != null && (
            <span className="text-[10px] text-text-dim">{st.durationMs.toFixed(2)} ms</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {stage !== "lexer" && (
            <button
              disabled={busy || !state.source.trim()}
              onClick={() => runOneStage(stage)}
              className="rounded border border-border bg-panel-raised px-2.5 py-1 text-[11px] text-text-primary hover:border-cyan hover:text-cyan disabled:opacity-40"
            >
              {state.mode === "running-stage" && state.runningStage === stage
                ? "running…"
                : `Run through ${STAGE_LABELS[stage]}`}
            </button>
          )}
          <button
            disabled={busy || !state.source.trim()}
            onClick={() => runAll()}
            className="rounded border border-cyan/40 bg-cyan-dim/30 px-2.5 py-1 text-[11px] font-medium text-cyan hover:bg-cyan-dim/50 disabled:opacity-40"
          >
            {state.mode === "running-all" ? "compiling…" : "Compile (run all)"}
          </button>
        </div>
      </div>
      {state.apiError && (
        <div className="border-b border-red/30 bg-red-dim/20 px-3 py-2 text-[12px] text-red">
          {state.apiError}
        </div>
      )}
      {st.status === "failed" && st.error && (
        <div className="border-b border-red/30 bg-red-dim/20 px-3 py-2 text-[12px] text-red">
          {st.error}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto p-3 space-y-3">
        {View ? <View data={state.results[stage]} /> : <p className="p-6 text-text-dim">Select a stage.</p>}
        {stage === "evolution" && state.stages.evolution.status === "completed" && (
          <BaselineComparisonPanel
            comparison={state.baseline}
            status={state.baselineStatus}
            error={state.baselineError}
            onRun={runBaselineComparison}
          />
        )}
      </div>
    </div>
  );
}
