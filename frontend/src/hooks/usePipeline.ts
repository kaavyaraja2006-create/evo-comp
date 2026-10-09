import { useCallback, useRef, useState } from "react";
import { CompilerApiError } from "../services/compilerApi";
import {
  compileOneShot,
  createSession,
  runStage as apiRunStage,
  runBaselineComparison as apiRunBaselineComparison,
} from "../services/pipelineApi";
import { STAGE_ORDER } from "../types/pipeline";
import type {
  BaselineComparison,
  CompileOptions,
  StageName,
  StageResult,
  StageStateDTO,
  StageStatus,
} from "../types/pipeline";

export type RunMode = "idle" | "running-stage" | "running-all";

export interface PipelineState {
  sessionId: string | null;
  source: string;
  options: CompileOptions;
  stages: Record<StageName, StageStateDTO>;
  results: Partial<Record<StageName, StageResult["data"]>>;
  mode: RunMode;
  runningStage: StageName | null;
  selectedStage: StageName;
  apiError: string | null;
  failedAt: StageName | null;
  baseline: BaselineComparison | null;
  baselineStatus: "idle" | "running" | "error";
  baselineError: string | null;
}

const EMPTY_STAGES: Record<StageName, StageStateDTO> = Object.fromEntries(
  STAGE_ORDER.map((s) => [s, { status: "not_started" as StageStatus, summary: null, error: null, durationMs: null }])
) as Record<StageName, StageStateDTO>;

const DEFAULT_OPTIONS: CompileOptions = { seed: 42, population: 16, generations: 14, step_limit: 200_000 };

export function usePipeline() {
  const [state, setState] = useState<PipelineState>({
    sessionId: null,
    source: "",
    options: DEFAULT_OPTIONS,
    stages: EMPTY_STAGES,
    results: {},
    mode: "idle",
    runningStage: null,
    selectedStage: "lexer",
    apiError: null,
    failedAt: null,
    baseline: null,
    baselineStatus: "idle",
    baselineError: null,
  });
  // avoids races if the user mashes buttons while a request is in flight
  const inFlight = useRef(0);

  const setSource = useCallback((source: string) => {
    setState((s) => ({ ...s, source }));
  }, []);

  const setOptions = useCallback((options: Partial<CompileOptions>) => {
    setState((s) => ({ ...s, options: { ...s.options, ...options } }));
  }, []);

  const reset = useCallback(() => {
    setState((s) => ({
      ...s,
      sessionId: null,
      stages: EMPTY_STAGES,
      results: {},
      apiError: null,
      failedAt: null,
      selectedStage: "lexer",
      baseline: null,
      baselineStatus: "idle",
      baselineError: null,
    }));
  }, []);

  const ensureSession = useCallback(async (): Promise<string> => {
    const existing = state.sessionId;
    if (existing) return existing;
    const summary = await createSession(state.source, state.options);
    setState((s) => ({ ...s, sessionId: summary.sessionId, stages: summary.stages, apiError: null }));
    return summary.sessionId;
  }, [state.sessionId, state.source, state.options]);

  const runOneStage = useCallback(
    async (stage: StageName) => {
      const token = ++inFlight.current;
      setState((s) => ({ ...s, mode: "running-stage", runningStage: stage, apiError: null }));
      try {
        // a fresh source/options edit always starts a new session
        const summary = await createSession(state.source, state.options);
        const sid = summary.sessionId;
        if (token !== inFlight.current) return;
        setState((s) => ({ ...s, sessionId: sid, stages: summary.stages }));
        // replay every stage up to and including the requested one, since a
        // brand-new session has nothing completed yet
        const idx = STAGE_ORDER.indexOf(stage);
        let last: StageResult | null = null;
        for (let i = 0; i <= idx; i++) {
          last = await apiRunStage(sid, STAGE_ORDER[i]);
          if (token !== inFlight.current) return;
          setState((s) => ({
            ...s,
            stages: { ...s.stages, [STAGE_ORDER[i]]: last as StageStateDTO },
            results: { ...s.results, [STAGE_ORDER[i]]: last!.data },
          }));
          if (last.status === "failed") break;
        }
        setState((s) => ({
          ...s,
          mode: "idle",
          runningStage: null,
          selectedStage: stage,
          failedAt: last && last.status === "failed" ? last.stage : null,
        }));
      } catch (err) {
        if (token !== inFlight.current) return;
        const msg = err instanceof CompilerApiError ? err.message : "Unexpected error running the pipeline.";
        setState((s) => ({ ...s, mode: "idle", runningStage: null, apiError: msg }));
      }
    },
    [state.source, state.options]
  );

  const runAll = useCallback(async () => {
    const token = ++inFlight.current;
    setState((s) => ({ ...s, mode: "running-all", runningStage: null, apiError: null }));
    try {
      const resp = await compileOneShot(state.source, state.options);
      if (token !== inFlight.current) return;
      setState((s) => ({
        ...s,
        sessionId: resp.sessionId,
        stages: resp.stages,
        results: resp.results ?? {},
        mode: "idle",
        failedAt: resp.failedAt,
        selectedStage: (resp.failedAt ?? "validation") as StageName,
        apiError: null,
      }));
    } catch (err) {
      if (token !== inFlight.current) return;
      const msg = err instanceof CompilerApiError ? err.message : "Unexpected error compiling.";
      setState((s) => ({ ...s, mode: "idle", apiError: msg }));
    }
  }, [state.source, state.options]);

  const selectStage = useCallback((stage: StageName) => {
    setState((s) => ({ ...s, selectedStage: stage }));
  }, []);

  // On-demand only: runs a full second evolutionary search with the Digital
  // Twin's correctness gate disabled and compares it to the gated run. Needs
  // a session that has already completed the Evolution stage.
  const runBaselineComparison = useCallback(async () => {
    const sid = state.sessionId;
    if (!sid) return;
    const token = ++inFlight.current;
    setState((s) => ({ ...s, baselineStatus: "running", baselineError: null }));
    try {
      const result = await apiRunBaselineComparison(sid);
      if (token !== inFlight.current) return;
      setState((s) => ({ ...s, baseline: result, baselineStatus: "idle" }));
    } catch (err) {
      if (token !== inFlight.current) return;
      const msg = err instanceof CompilerApiError ? err.message : "Unexpected error running the baseline comparison.";
      setState((s) => ({ ...s, baselineStatus: "error", baselineError: msg }));
    }
  }, [state.sessionId]);

  return {
    state, setSource, setOptions, reset, runOneStage, runAll, selectStage, ensureSession,
    runBaselineComparison,
  };
}
