import type {
  BaselineComparison,
  CompileOptions,
  CompileResponse,
  SessionSummary,
  StageName,
  StageResult,
  StagesMetaResponse,
} from "../types/pipeline";
import { CompilerApiError } from "./compilerApi";

const API_BASE = "/api";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new CompilerApiError(
      "Could not reach the EVO-COMP backend. Is the FastAPI server running on port 8000?"
    );
  }
  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      // ignore body parse failure, keep generic message
    }
    const err = new CompilerApiError(detail) as CompilerApiError & { status?: number; body?: unknown };
    err.status = res.status;
    throw err;
  }
  return (await res.json()) as T;
}

export function fetchStagesMeta(): Promise<StagesMetaResponse> {
  return call<StagesMetaResponse>("/stages");
}

export function createSession(source: string, options?: Partial<CompileOptions>): Promise<SessionSummary> {
  return call<SessionSummary>("/session", {
    method: "POST",
    body: JSON.stringify({ source, options: options ?? null }),
  });
}

export function getSession(sessionId: string): Promise<SessionSummary> {
  return call<SessionSummary>(`/session/${sessionId}`);
}

export function runStage(sessionId: string, stage: StageName): Promise<StageResult> {
  return call<StageResult>(`/session/${sessionId}/run/${stage}`, { method: "POST" });
}

export function getStage(sessionId: string, stage: StageName): Promise<StageResult> {
  return call<StageResult>(`/session/${sessionId}/stage/${stage}`);
}

export function runAll(sessionId: string): Promise<SessionSummary> {
  return call<SessionSummary>(`/session/${sessionId}/run-all`, { method: "POST" });
}

export function compileOneShot(source: string, options?: Partial<CompileOptions>): Promise<CompileResponse> {
  return call<CompileResponse>("/compile", {
    method: "POST",
    body: JSON.stringify({ source, options: options ?? null }),
  });
}

// Runs a full second evolutionary search with the Digital Twin's correctness
// gate disabled and compares it to the gated run. Materially slower than any
// other call here (it's a second search from scratch) - only call it when
// the user explicitly asks to see the baseline comparison.
export function runBaselineComparison(sessionId: string): Promise<BaselineComparison> {
  return call<BaselineComparison>(`/session/${sessionId}/baseline-comparison`, { method: "POST" });
}
