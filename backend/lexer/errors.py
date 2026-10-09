

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LexicalError:
   

    message: str
    line: int
    column: int
    character: str = ""

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "character": self.character,
        }
