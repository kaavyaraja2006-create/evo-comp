"""API routes for EVO-COMP Phase 2+: parser through final validation.

Two ways to drive the pipeline:
  * stage-by-stage (session-based) — matches the "research lab" UI, where
    each stage is a button the user presses in order and inspects;
  * one-shot ``/compile`` — runs every stage and returns the full report,
    for a single "compile" action or for scripted/test use.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from pipeline import store
from pipeline.pipeline import BaselineUnavailable, RUNNERS, run_all, run_baseline_comparison_for_session, run_stage
from pipeline.session import DEPENDS, STAGE_META, STAGES, CompileOptions, StageBlocked

from .pipeline_models import (
    CompileOptionsRequest,
    CompileRequest,
    ErrorResponse,
    SessionCreateRequest,
    SessionSummaryResponse,
    StageResultResponse,
)

router = APIRouter()


def _options(req: Optional[CompileOptionsRequest]) -> CompileOptions:
    if req is None:
        return CompileOptions()
    return CompileOptions(seed=req.seed, population=req.population, generations=req.generations,
                          step_limit=req.step_limit)


def _next_stage(stage: str) -> Optional[str]:
    i = STAGES.index(stage)
    return STAGES[i + 1] if i + 1 < len(STAGES) else None


def _get_session(session_id: str):
    s = store.get(session_id)
    if s is None:
        raise HTTPException(404, f"No session '{session_id}' (it may have expired; sessions are in-memory "
                                 f"and capped at {store.MAX_SESSIONS})")
    return s


@router.get("/stages")
def list_stages():
    """Static metadata the UI uses to render the pipeline sidebar: labels,
    button text, loading messages and the input/transformation/output
    description for every stage, in dependency order."""
    return {"order": STAGES, "depends": DEPENDS, "stages": STAGE_META}


@router.post("/session", response_model=SessionSummaryResponse)
def create_session(req: SessionCreateRequest):
    try:
        s = store.create(req.source, _options(req.options))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return s.summary()


@router.get("/session/{session_id}", response_model=SessionSummaryResponse)
def get_session(session_id: str):
    return _get_session(session_id).summary()


@router.delete("/session/{session_id}")
def delete_session(session_id: str):
    if not store.delete(session_id):
        raise HTTPException(404, f"No session '{session_id}'")
    return {"deleted": session_id}


@router.get("/session/{session_id}/stage/{stage}", response_model=StageResultResponse)
def get_stage(session_id: str, stage: str):
    if stage not in RUNNERS:
        raise HTTPException(404, f"Unknown stage '{stage}'. Valid stages: {STAGES}")
    s = _get_session(session_id)
    st = s.stages[stage]
    return StageResultResponse(sessionId=session_id, stage=stage, status=st.status, summary=st.summary,
                               error=st.error, durationMs=st.duration_ms, data=st.data,
                               nextStage=_next_stage(stage))


@router.post("/session/{session_id}/run/{stage}", response_model=StageResultResponse)
def run_one_stage(session_id: str, stage: str):
    if stage not in RUNNERS:
        raise HTTPException(404, f"Unknown stage '{stage}'. Valid stages: {STAGES}")
    s = _get_session(session_id)
    try:
        st = run_stage(s, stage)
    except StageBlocked as b:
        raise HTTPException(409, detail={"error": b.reason, "stage": stage, "blockedBy": b.blocked_by})
    return StageResultResponse(sessionId=session_id, stage=stage, status=st.status, summary=st.summary,
                               error=st.error, durationMs=st.duration_ms, data=st.data,
                               nextStage=_next_stage(stage) if st.status == "completed" else None)


@router.post("/session/{session_id}/run-all", response_model=SessionSummaryResponse)
def run_all_stages(session_id: str):
    """Run every stage from the beginning, stopping at the first failure."""
    s = _get_session(session_id)
    run_all(s)
    return s.summary()


@router.get("/session/{session_id}/report")
def get_report(session_id: str):
    s = _get_session(session_id)
    data = s.stages["validation"].data
    if data is None or "report" not in data:
        raise HTTPException(409, "Validation has not produced a report yet; run the pipeline through "
                                 "the validation stage first.")
    return data["report"]


@router.post("/session/{session_id}/baseline-comparison")
def baseline_comparison(session_id: str):
    """On-demand: run the evolutionary search a second time with the Digital
    Twin's correctness gate disabled, and report a real, measured comparison
    against the gated run already produced by the Evolution stage. This runs
    a full second search, so it is materially slower than any other endpoint
    here and is never called automatically."""
    s = _get_session(session_id)
    try:
        return run_baseline_comparison_for_session(s)
    except BaselineUnavailable as e:
        raise HTTPException(409, str(e))


@router.post("/compile")
def compile_one_shot(req: CompileRequest):
    """Create a session and run the full pipeline in one call. Returns the
    stage-by-stage summary plus, if the pipeline reached validation, the
    final report."""
    try:
        s = store.create(req.source, _options(req.options))
    except ValueError as e:
        raise HTTPException(422, str(e))
    failed_at = run_all(s)
    out = s.full()
    out["failedAt"] = failed_at
    val = s.stages["validation"].data
    out["report"] = val["report"] if (val and "report" in val) else None
    return out
