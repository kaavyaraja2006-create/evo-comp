"""API routes for EVO-COMP Phase 1 — Lexical Analysis."""

from __future__ import annotations

import time

from fastapi import APIRouter

from lexer.lexer import Lexer
from models.compilation import (
    LexicalErrorModel,
    LexRequest,
    LexResponse,
    LexerPerformance,
    TokenModel,
    compute_statistics,
)

router = APIRouter()


@router.post("/lex", response_model=LexResponse)
def lex_source(request: LexRequest) -> LexResponse:
    """Tokenize EvoLang source code using the real EvoLang lexer.

    Every field in the response is derived directly from executing the
    lexer against `request.source` — nothing here is precomputed or
    hardcoded.
    """
    source = request.source

    started = time.perf_counter()
    result = Lexer(source).tokenize()
    elapsed_ms = (time.perf_counter() - started) * 1000

    statistics = compute_statistics(result.tokens)

    return LexResponse(
        success=result.success,
        tokens=[TokenModel(**tok.to_dict()) for tok in result.tokens],
        statistics=statistics,
        errors=[LexicalErrorModel(**err.to_dict()) for err in result.errors],
        performance=LexerPerformance(
            inputSizeCharacters=len(source),
            inputSizeLines=source.count("\n") + 1 if source else 0,
            tokensGenerated=len(result.tokens),
            lexingTimeMs=round(elapsed_ms, 4),
        ),
    )
