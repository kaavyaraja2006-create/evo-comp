from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TokenType(str, Enum):

    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    INTEGER_LITERAL = "INTEGER_LITERAL"
    FLOAT_LITERAL = "FLOAT_LITERAL"
    STRING_LITERAL = "STRING_LITERAL"
    BOOLEAN_LITERAL = "BOOLEAN_LITERAL"
    OPERATOR = "OPERATOR"
    DELIMITER = "DELIMITER"
    COMMENT = "COMMENT"
    EOF = "EOF"


@dataclass
class Token:


    index: int
    type: TokenType
    value: Any
    lexeme: str
    line: int
    column: int
    start: int
    end: int

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "type": self.type.value,
            "value": self.value,
            "lexeme": self.lexeme,
            "line": self.line,
            "column": self.column,
            "start": self.start,
            "end": self.end,
        }


# EvoLang reserved keywords.
KEYWORDS = {
    "int",
    "float",
    "string",
    "bool",
    "if",
    "else",
    "for",
    "while",
    "return",
    "function",
    "print",
}


BOOLEAN_LITERALS = {"true", "false"}


MULTI_CHAR_OPERATORS = [
    "==",
    "!=",
    "<=",
    ">=",
    "&&",
    "||",
    "+=",
    "-=",
    "*=",
    "/=",
    "++",
    "--",
]

SINGLE_CHAR_OPERATORS = set("+-*/%=<>!")

DELIMITERS = set("(){}[];,.")
