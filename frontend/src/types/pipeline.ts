// Mirrors backend/pipeline/session.py + the per-stage JSON shapes produced
// by backend/pipeline/pipeline.py. Nested stage payloads are large and
// stage-specific, so most are typed loosely (Record<string, unknown> /
// well-known top-level keys) rather than exhaustively — components read
// the real fields they need directly off the response.

export const STAGE_ORDER = [
  "lexer", "parser", "ast", "semantic", "ir", "cfg", "dna",
  "evolution", "twin", "codegen", "evovm", "execution", "validation",
] as const;

export type StageName = (typeof STAGE_ORDER)[number];

export type StageStatus = "not_started" | "completed" | "failed";

export interface StageMeta {
  label: string;
  button: string;
  loading: string[];
  input: string;
  transformation: string;
  output: string;
  explanation: string;
}

export interface StagesMetaResponse {
  order: StageName[];
  depends: Record<StageName, StageName | null>;
  stages: Record<StageName, StageMeta>;
}

export interface StageStateDTO {
  status: StageStatus;
  summary: string | null;
  error: string | null;
  durationMs: number | null;
}

export interface CompileOptions {
  seed: number;
  population: number;
  generations: number;
  step_limit: number;
}

export interface SessionSummary {
  sessionId: string;
  source: { lines: number; characters: number };
  options: CompileOptions;
  order: StageName[];
  stages: Record<StageName, StageStateDTO>;
}

export interface StageResult {
  sessionId: string;
  stage: StageName;
  status: StageStatus;
  summary: string | null;
  error: string | null;
  durationMs: number | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
  nextStage: StageName | null;
}

export interface CompileResponse extends SessionSummary {
  failedAt: StageName | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  results: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  report: Record<string, any> | null;
}

export interface BlockedError {
  error: string;
  stage: StageName;
  blockedBy: StageName | null;
}

export interface BaselineCandidateSummary {
  label: string;
  found: boolean;
  candidateId?: string;
  genome?: string[];
  fitness?: number;
  staticSize?: number;
  dynamicCost?: number;
  dynamicCostReductionPercent?: number;
  staticSizeReductionPercent?: number;
  actuallyCorrect?: boolean;
}

export interface BaselineComparison {
  seed: number;
  population: number;
  generations: number;
  original: { staticSize: number; dynamicCost: number };
  gated: BaselineCandidateSummary;
  ungated: BaselineCandidateSummary;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  gatedStatistics: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ungatedStatistics: Record<string, any>;
  incorrectCandidateWouldShip: boolean;
  speedGapPercentagePoints: number | null;
  headline: string;
  methodology: string;
}
