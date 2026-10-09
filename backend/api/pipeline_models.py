"""Request/response models for the compiler-pipeline API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from pipeline.session import STAGES


class CompileOptionsRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    population: int = Field(default=16, ge=1, le=64)
    generations: int = Field(default=14, ge=1, le=60)
    step_limit: int = Field(default=200_000, ge=1_000, le=5_000_000)


class SessionCreateRequest(BaseModel):
    source: str = Field(default="", description="EvoLang source code")
    options: Optional[CompileOptionsRequest] = None


class CompileRequest(SessionCreateRequest):
    pass


class StageResultResponse(BaseModel):
    sessionId: str
    stage: str
    status: str
    summary: Optional[str] = None
    error: Optional[str] = None
    durationMs: Optional[float] = None
    data: Optional[Dict[str, Any]] = None
    nextStage: Optional[str] = None


class SessionSummaryResponse(BaseModel):
    sessionId: str
    source: Dict[str, int]
    options: Dict[str, Any]
    order: List[str] = Field(default_factory=lambda: list(STAGES))
    stages: Dict[str, Dict[str, Any]]


class ErrorResponse(BaseModel):
    error: str
    stage: Optional[str] = None
    blockedBy: Optional[str] = None
