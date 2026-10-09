"""
Request/response models for the /api/lex endpoint, and the statistics
computation that derives real numbers from a real token stream.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from lexer.token import Token, TokenType


class LexRequest(BaseModel):
    source: str = Field(default="", description="EvoLang source code to tokenize")


class TokenModel(BaseModel):
    index: int
    type: str
    value: Any
    lexeme: str
    line: int
    column: int
    start: int
    end: int


class LexicalErrorModel(BaseModel):
    message: str
    line: int
    column: int
    character: str = ""


class TokenStatistics(BaseModel):
    totalTokens: int
    keywords: int
    identifiers: int
    integerLiterals: int
    floatLiterals: int
    stringLiterals: int
    booleanLiterals: int
    literals: int
    operators: int
    delimiters: int
    comments: int
    eof: int


class LexerPerformance(BaseModel):
    inputSizeCharacters: int
    inputSizeLines: int
    tokensGenerated: int
    lexingTimeMs: float


class LexResponse(BaseModel):
    success: bool
    tokens: List[TokenModel]
    statistics: TokenStatistics
    errors: List[LexicalErrorModel]
    performance: LexerPerformance


_LITERAL_TYPES = {
    TokenType.INTEGER_LITERAL,
    TokenType.FLOAT_LITERAL,
    TokenType.STRING_LITERAL,
    TokenType.BOOLEAN_LITERAL,
}


def compute_statistics(tokens: List[Token]) -> TokenStatistics:
    """Derive every statistic strictly from the actual token list.

    No value here is hardcoded or estimated — each counter is a tally
    over the real tokens the lexer produced for this specific source.
    """
    counts = {t: 0 for t in TokenType}
    for tok in tokens:
        counts[tok.type] += 1

    literal_count = sum(counts[t] for t in _LITERAL_TYPES)

    return TokenStatistics(
        totalTokens=len(tokens),
        keywords=counts[TokenType.KEYWORD],
        identifiers=counts[TokenType.IDENTIFIER],
        integerLiterals=counts[TokenType.INTEGER_LITERAL],
        floatLiterals=counts[TokenType.FLOAT_LITERAL],
        stringLiterals=counts[TokenType.STRING_LITERAL],
        booleanLiterals=counts[TokenType.BOOLEAN_LITERAL],
        literals=literal_count,
        operators=counts[TokenType.OPERATOR],
        delimiters=counts[TokenType.DELIMITER],
        comments=counts[TokenType.COMMENT],
        eof=counts[TokenType.EOF],
    )
