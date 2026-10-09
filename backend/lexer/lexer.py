from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .errors import LexicalError
from .token import (
    BOOLEAN_LITERALS,
    DELIMITERS,
    KEYWORDS,
    MULTI_CHAR_OPERATORS,
    SINGLE_CHAR_OPERATORS,
    Token,
    TokenType,
)


def _is_identifier_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_identifier_part(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


@dataclass
class LexResult:
    success: bool
    tokens: List[Token] = field(default_factory=list)
    errors: List[LexicalError] = field(default_factory=list)


class Lexer:
    """Scans EvoLang source text into a stream of tokens."""

    def __init__(self, source: str):
        self.source = source
        self.length = len(source)
        self.pos = 0  # absolute character offset
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        self.errors: List[LexicalError] = []
        self._token_index = 0

    # -- low level character helpers -----------------------------------

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= self.length:
            return ""
        return self.source[idx]

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _at_end(self) -> bool:
        return self.pos >= self.length

    def _next_index(self) -> int:
        self._token_index += 1
        return self._token_index

    def _emit(self, type_: TokenType, value, lexeme: str, start_pos: int,
              start_line: int, start_col: int) -> None:
        self.tokens.append(
            Token(
                index=self._next_index(),
                type=type_,
                value=value,
                lexeme=lexeme,
                line=start_line,
                column=start_col,
                start=start_pos,
                end=self.pos,
            )
        )

    # -- main driver ------------------------------------------------------

    def tokenize(self) -> LexResult:
        while not self._at_end():
            ch = self._peek()

            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
                continue

            if ch == "/" and self._peek(1) == "/":
                self._scan_line_comment()
                continue

            if ch == "/" and self._peek(1) == "*":
                self._scan_block_comment()
                continue

            if ch == '"':
                self._scan_string()
                continue

            if ch.isdigit():
                self._scan_number()
                continue

            if _is_identifier_start(ch):
                self._scan_identifier_or_keyword()
                continue

            if self._scan_operator():
                continue

            if ch in DELIMITERS:
                start_pos, start_line, start_col = self.pos, self.line, self.column
                self._advance()
                self._emit(TokenType.DELIMITER, ch, ch, start_pos, start_line, start_col)
                continue

            # Unrecognized character -> lexical error, then skip it so
            # scanning can continue and surface further diagnostics.
            start_line, start_col = self.line, self.column
            bad_char = self._advance()
            self.errors.append(
                LexicalError(
                    message=f"Unexpected character '{bad_char}'",
                    line=start_line,
                    column=start_col,
                    character=bad_char,
                )
            )

        # Always emit EOF on a successful (or partially successful) scan.
        self._emit(TokenType.EOF, None, "", self.pos, self.line, self.column)

        return LexResult(
            success=len(self.errors) == 0,
            tokens=self.tokens,
            errors=self.errors,
        )

    # -- scanning routines -------------------------------------------------

    def _scan_line_comment(self) -> None:
        start_pos, start_line, start_col = self.pos, self.line, self.column
        chars = []
        while not self._at_end() and self._peek() != "\n":
            chars.append(self._advance())
        lexeme = "".join(chars)
        self._emit(TokenType.COMMENT, lexeme, lexeme, start_pos, start_line, start_col)

    def _scan_block_comment(self) -> None:
        start_pos, start_line, start_col = self.pos, self.line, self.column
        chars = [self._advance(), self._advance()]  # consume '/*'
        terminated = False
        while not self._at_end():
            if self._peek() == "*" and self._peek(1) == "/":
                chars.append(self._advance())
                chars.append(self._advance())
                terminated = True
                break
            chars.append(self._advance())
        lexeme = "".join(chars)
        if not terminated:
            self.errors.append(
                LexicalError(
                    message="Unterminated block comment",
                    line=start_line,
                    column=start_col,
                    character="/*",
                )
            )
        self._emit(TokenType.COMMENT, lexeme, lexeme, start_pos, start_line, start_col)

    def _scan_string(self) -> None:
        start_pos, start_line, start_col = self.pos, self.line, self.column
        self._advance()  # opening quote
        chars = []
        terminated = False
        while not self._at_end():
            ch = self._peek()
            if ch == '"':
                self._advance()
                terminated = True
                break
            if ch == "\n":
                # A newline before the closing quote means the string
                # was never terminated on this line.
                break
            if ch == "\\" and self._peek(1) != "":
                # Consume a simple escape sequence (\", \\, \n, \t, ...).
                self._advance()
                escaped = self._advance()
                chars.append(_unescape(escaped))
                continue
            chars.append(self._advance())

        raw_lexeme = self.source[start_pos:self.pos]
        value = "".join(chars)

        if not terminated:
            self.errors.append(
                LexicalError(
                    message="Unterminated string literal",
                    line=start_line,
                    column=start_col,
                    character='"',
                )
            )

        self._emit(
            TokenType.STRING_LITERAL, value, raw_lexeme, start_pos, start_line, start_col
        )

    def _scan_number(self) -> None:
        start_pos, start_line, start_col = self.pos, self.line, self.column
        chars = []
        while not self._at_end() and self._peek().isdigit():
            chars.append(self._advance())

        is_float = False
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            chars.append(self._advance())  # consume '.'
            while not self._at_end() and self._peek().isdigit():
                chars.append(self._advance())

        lexeme = "".join(chars)
        if is_float:
            self._emit(
                TokenType.FLOAT_LITERAL, float(lexeme), lexeme, start_pos, start_line, start_col
            )
        else:
            self._emit(
                TokenType.INTEGER_LITERAL, int(lexeme), lexeme, start_pos, start_line, start_col
            )

    def _scan_identifier_or_keyword(self) -> None:
        start_pos, start_line, start_col = self.pos, self.line, self.column
        chars = []
        while not self._at_end() and _is_identifier_part(self._peek()):
            chars.append(self._advance())
        lexeme = "".join(chars)

        if lexeme in BOOLEAN_LITERALS:
            value = lexeme == "true"
            self._emit(
                TokenType.BOOLEAN_LITERAL, value, lexeme, start_pos, start_line, start_col
            )
        elif lexeme in KEYWORDS:
            self._emit(TokenType.KEYWORD, lexeme, lexeme, start_pos, start_line, start_col)
        else:
            self._emit(
                TokenType.IDENTIFIER, lexeme, lexeme, start_pos, start_line, start_col
            )

    def _scan_operator(self) -> bool:
        """Attempt to scan a (possibly multi-character) operator using
        maximal munch. Returns False if the current character is not the
        start of any known operator."""
        two_char = self._peek() + self._peek(1)
        if two_char in MULTI_CHAR_OPERATORS:
            start_pos, start_line, start_col = self.pos, self.line, self.column
            self._advance()
            self._advance()
            self._emit(TokenType.OPERATOR, two_char, two_char, start_pos, start_line, start_col)
            return True

        ch = self._peek()
        if ch in SINGLE_CHAR_OPERATORS:
            start_pos, start_line, start_col = self.pos, self.line, self.column
            self._advance()
            self._emit(TokenType.OPERATOR, ch, ch, start_pos, start_line, start_col)
            return True

        return False


def _unescape(ch: str) -> str:
    return {
        "n": "\n",
        "t": "\t",
        "r": "\r",
        '"': '"',
        "\\": "\\",
    }.get(ch, ch)
