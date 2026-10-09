"""Recursive-descent parser for EvoLang.

Consumes the *real* token stream produced by the Phase 1 lexer (COMMENT
tokens are filtered out, as the Phase 1 README specifies) and builds typed
AST nodes. See ``docs/GRAMMAR.md`` for the grammar this file implements; the
parser implements nothing that document does not list.
"""

from __future__ import annotations

import functools
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lexer.token import Token, TokenType
from compiler.ast import nodes as N

TYPE_KEYWORDS = ("int", "float", "string", "bool")
ASSIGN_OPS = ("=", "+=", "-=", "*=", "/=")
STATEMENT_START_KEYWORDS = ("if", "while", "for", "return", "print", "function",
                            "int", "float", "string", "bool")

# Rules that are written to the (preorder) parse trace. Every rule is counted
# in ``rule_counts``; only these structural ones are listed individually so the
# trace stays readable.
TRACED_RULES = {
    "program", "functionDecl", "block", "varDecl", "assignment", "incDec",
    "exprStmt", "ifStmt", "whileStmt", "forStmt", "returnStmt", "printStmt",
    "params", "expression",
}
MAX_TRACE = 4000
MAX_ERRORS = 25


class ParseError(Exception):
    def __init__(self, message: str, token: Token, expected: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.token = token
        self.expected = expected
        self.hint = hint


def _describe(tok: Token) -> str:
    if tok.type == TokenType.EOF:
        return "end of file"
    return tok.lexeme


def _end_pos(tok: Token):
    lx = tok.lexeme
    if "\n" in lx:
        return tok.line + lx.count("\n"), len(lx) - lx.rfind("\n")
    return tok.line, tok.column + len(lx)


def _span(first: Token, last: Token) -> N.Span:
    el, ec = _end_pos(last)
    return N.Span(first.line, first.column, el, ec, first.start, last.end,
                  first.index, last.index)


def _join(a: N.Span, b: N.Span) -> N.Span:
    return N.Span(a.line, a.column, b.end_line, b.end_column, a.start, b.end,
                  a.first_token, b.last_token)


def rule(name: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            self.rule_counts[name] += 1
            self.depth += 1
            self.max_depth = max(self.max_depth, self.depth)
            entry = None
            if name in TRACED_RULES and len(self.trace) < MAX_TRACE:
                entry = {"rule": name, "depth": self.depth,
                         "startToken": self.toks[self.i].index,
                         "endToken": None, "status": "failed"}
                self.trace.append(entry)
            try:
                result = fn(self, *args, **kwargs)
            finally:
                self.depth -= 1
            if entry is not None:
                entry["endToken"] = self.toks[self.i - 1].index if self.i > 0 else entry["startToken"]
                entry["status"] = "ok"
            return result
        return wrapper
    return deco


@dataclass
class ParseResult:
    success: bool
    program: Optional[N.Program]
    errors: List[dict] = field(default_factory=list)
    tokens_total: int = 0
    tokens_consumed: int = 0
    comments_skipped: int = 0
    rule_counts: Dict[str, int] = field(default_factory=dict)
    trace: List[dict] = field(default_factory=list)
    max_depth: int = 0
    parse_ms: float = 0.0
    node_count: int = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": "SUCCESS" if self.success else "FAILED",
            "tokensTotal": self.tokens_total,
            "tokensRead": self.tokens_consumed,
            "commentsSkipped": self.comments_skipped,
            "astNodes": self.node_count if self.success else None,
            "errors": self.errors,
            "ruleCounts": dict(sorted(self.rule_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
            "ruleInvocations": sum(self.rule_counts.values()),
            "maxRecursionDepth": self.max_depth,
            "trace": self.trace,
            "traceTruncated": len(self.trace) >= MAX_TRACE,
            "parseMs": round(self.parse_ms, 4),
            "strategy": "recursive descent, one method per grammar production, "
                        "statement-level panic-mode error recovery",
        }


class Parser:
    def __init__(self, tokens: List[Token]):
        self.all_tokens = tokens
        self.toks = [t for t in tokens if t.type != TokenType.COMMENT]
        self.comments_skipped = len(tokens) - len(self.toks)
        if not self.toks or self.toks[-1].type != TokenType.EOF:
            raise ValueError("token stream must end with EOF")
        self.i = 0
        self.errors: List[dict] = []
        self.rule_counts: Counter = Counter()
        self.trace: List[dict] = []
        self.depth = 0
        self.max_depth = 0

    # ---- token helpers ------------------------------------------------
    def peek(self, k: int = 0) -> Token:
        j = min(self.i + k, len(self.toks) - 1)
        return self.toks[j]

    def prev(self) -> Token:
        return self.toks[self.i - 1]

    def advance(self) -> Token:
        t = self.toks[self.i]
        if t.type != TokenType.EOF:
            self.i += 1
        return t

    def at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

    def is_kw(self, lexeme: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t.type == TokenType.KEYWORD and t.lexeme == lexeme

    def is_type_kw(self, k: int = 0) -> bool:
        t = self.peek(k)
        return t.type == TokenType.KEYWORD and t.lexeme in TYPE_KEYWORDS

    def is_op(self, *lexemes: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t.type == TokenType.OPERATOR and t.lexeme in lexemes

    def is_delim(self, lexeme: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t.type == TokenType.DELIMITER and t.lexeme == lexeme

    def error(self, expected: str, hint: str = "", message: Optional[str] = None) -> ParseError:
        return ParseError(message or f"Expected {expected}", self.peek(), expected, hint)

    def expect_delim(self, lexeme: str, hint: str = "") -> Token:
        if self.is_delim(lexeme):
            return self.advance()
        raise self.error(f"'{lexeme}'", hint)

    def expect_ident(self, what: str = "identifier") -> Token:
        if self.peek().type == TokenType.IDENTIFIER:
            return self.advance()
        raise self.error(what)

    # ---- driver -------------------------------------------------------
    def parse(self) -> ParseResult:
        t0 = time.perf_counter()
        program: Optional[N.Program] = None
        try:
            program = self.parse_program()
        except RecursionError:
            self._record(ParseError("Program is nested too deeply to parse", self.peek(), "shallower nesting"))
        ms = (time.perf_counter() - t0) * 1000
        ok = not self.errors
        count = sum(1 for _ in N.walk(program)) if (ok and program) else 0
        return ParseResult(
            success=ok, program=program if ok else None, errors=self.errors,
            tokens_total=len(self.toks), tokens_consumed=self.i + (1 if self.at_end() else 0),
            comments_skipped=self.comments_skipped, rule_counts=dict(self.rule_counts),
            trace=self.trace, max_depth=self.max_depth, parse_ms=ms, node_count=count,
        )

    def _record(self, err: ParseError) -> None:
        t = err.token
        self.errors.append({
            "message": err.message, "line": t.line, "column": t.column,
            "expected": err.expected, "found": _describe(t),
            "foundType": t.type.value, "tokenIndex": t.index, "hint": err.hint,
            "start": t.start, "end": t.end,
        })

    def synchronize(self, start_pos: int) -> None:
        """Panic-mode recovery: skip to just after ';' or just before a
        block end / statement keyword, always making progress."""
        while not self.at_end():
            if self.is_delim(";"):
                self.advance()
                return
            if self.is_delim("}"):
                return
            t = self.peek()
            if self.i > start_pos and t.type == TokenType.KEYWORD and t.lexeme in STATEMENT_START_KEYWORDS:
                return
            self.advance()
        return

    # ---- productions --------------------------------------------------
    @rule("program")
    def parse_program(self) -> N.Program:
        first = self.peek()
        body: List[N.Node] = []
        while not self.at_end():
            start = self.i
            try:
                body.append(self.parse_item())
            except ParseError as e:
                self._record(e)
                if len(self.errors) >= MAX_ERRORS:
                    break
                self.synchronize(start)
                if self.i == start:
                    self.advance()
        eof = self.peek()
        prog = N.Program(body=body)
        prog.span = N.Span(1, 1, eof.line, eof.column, 0, eof.end, self.toks[0].index, eof.index)
        return prog

    def parse_item(self) -> N.Node:
        if self.is_kw("function") or (
            self.is_type_kw() and self.peek(1).type == TokenType.IDENTIFIER and self.is_delim("(", k=2)
        ):
            return self.parse_function_decl()
        return self.parse_statement()

    @rule("functionDecl")
    def parse_function_decl(self) -> N.FunctionDeclaration:
        first = self.peek()
        ret: Optional[str] = None
        if self.is_kw("function"):
            self.advance()
            form = "function"
        else:
            ret = self.advance().lexeme
            form = "typed"
        name_tok = self.expect_ident("function name")
        self.expect_delim("(", "function parameter list")
        params = self.parse_params()
        self.expect_delim(")", "end of parameter list")
        if not self.is_delim("{"):
            raise self.error("'{'", "function body")
        body = self.parse_block()
        fn = N.FunctionDeclaration(name=name_tok.lexeme, return_type=ret, params=params, body=body, form=form)
        fn.span = _span(first, self.prev())
        return fn

    @rule("params")
    def parse_params(self) -> List[N.Parameter]:
        params: List[N.Parameter] = []
        if self.is_delim(")"):
            return params
        while True:
            if not self.is_type_kw():
                raise self.error("parameter type", "one of int, float, string, bool")
            ttok = self.advance()
            ntok = self.expect_ident("parameter name")
            p = N.Parameter(name=ntok.lexeme, type=ttok.lexeme)
            p.span = _span(ttok, ntok)
            params.append(p)
            if self.is_delim(","):
                self.advance()
                continue
            break
        return params

    def parse_statement(self) -> N.Node:
        t = self.peek()
        if t.type == TokenType.DELIMITER and t.lexeme == "{":
            return self.parse_block()
        if t.type == TokenType.KEYWORD:
            kw = t.lexeme
            if kw == "if":
                return self.parse_if()
            if kw == "while":
                return self.parse_while()
            if kw == "for":
                return self.parse_for()
            if kw == "return":
                return self.parse_return()
            if kw == "print":
                return self.parse_print()
            if kw == "function" or (kw in TYPE_KEYWORDS and self.peek(1).type == TokenType.IDENTIFIER
                                    and self.is_delim("(", k=2)):
                if self.depth > 1:
                    raise ParseError("Function declarations are only allowed at the top level", t,
                                     "statement", "move the function outside of any block")
            if kw in TYPE_KEYWORDS:
                node = self.parse_var_decl()
                self.expect_delim(";", "end of variable declaration")
                node.span = _span(t, self.prev())
                return node
            if kw == "else":
                raise ParseError("'else' without a matching 'if'", t, "statement")
        if t.type == TokenType.IDENTIFIER:
            node = self.parse_simple_statement()
            self.expect_delim(";", "end of statement")
            node.span = _span(t, self.prev())
            return node
        if t.type == TokenType.DELIMITER and t.lexeme in ("[", "]", "."):
            raise ParseError(f"Unexpected '{t.lexeme}' (arrays and member access are not part of the supported grammar)",
                             t, "statement")
        raise self.error("statement")

    @rule("block")
    def parse_block(self) -> N.BlockStatement:
        first = self.expect_delim("{")
        stmts: List[N.Node] = []
        while not self.is_delim("}") and not self.at_end():
            start = self.i
            try:
                stmts.append(self.parse_statement())
            except ParseError as e:
                self._record(e)
                if len(self.errors) >= MAX_ERRORS:
                    raise _Abort()
                self.synchronize(start)
                if self.i == start:
                    self.advance()
        if not self.is_delim("}"):
            raise self.error("'}'", "unclosed block")
        self.advance()
        b = N.BlockStatement(statements=stmts)
        b.span = _span(first, self.prev())
        return b

    @rule("varDecl")
    def parse_var_decl(self) -> N.VariableDeclaration:
        ttok = self.advance()
        ntok = self.expect_ident("variable name")
        init = None
        if self.is_op("="):
            self.advance()
            init = self.parse_expression()
        d = N.VariableDeclaration(var_type=ttok.lexeme, name=ntok.lexeme, init=init)
        d.span = _span(ttok, self.prev())
        return d

    def parse_simple_statement(self) -> N.Node:
        """assignment | incDec | call  (no trailing ';')"""
        t = self.peek()
        nxt = self.peek(1)
        if nxt.type == TokenType.DELIMITER and nxt.lexeme == "(":
            return self._expr_stmt()
        if nxt.type == TokenType.OPERATOR and nxt.lexeme in ASSIGN_OPS:
            return self._assignment()
        if nxt.type == TokenType.OPERATOR and nxt.lexeme in ("++", "--"):
            return self._incdec()
        self.advance()  # point the error at what follows the identifier
        raise self.error("assignment, '++', '--' or '(' after identifier")

    @rule("exprStmt")
    def _expr_stmt(self) -> N.ExpressionStatement:
        first = self.peek()
        call = self.parse_call()
        s = N.ExpressionStatement(expression=call)
        s.span = _span(first, self.prev())
        return s

    @rule("assignment")
    def _assignment(self) -> N.Assignment:
        ttok = self.advance()
        target = N.Identifier(name=ttok.lexeme)
        target.span = _span(ttok, ttok)
        op = self.advance().lexeme
        value = self.parse_expression()
        a = N.Assignment(target=target, operator=op, value=value)
        a.span = _span(ttok, self.prev())
        return a

    @rule("incDec")
    def _incdec(self) -> N.IncDecStatement:
        ttok = self.advance()
        target = N.Identifier(name=ttok.lexeme)
        target.span = _span(ttok, ttok)
        op = self.advance().lexeme
        s = N.IncDecStatement(target=target, operator=op)
        s.span = _span(ttok, self.prev())
        return s

    @rule("ifStmt")
    def parse_if(self) -> N.IfStatement:
        first = self.advance()
        self.expect_delim("(", "condition of 'if'")
        cond = self.parse_expression()
        self.expect_delim(")", "end of 'if' condition")
        then = self.parse_statement()
        els = None
        if self.is_kw("else"):
            self.advance()
            els = self.parse_statement()
        n = N.IfStatement(condition=cond, then_branch=then, else_branch=els)
        n.span = _span(first, self.prev())
        return n

    @rule("whileStmt")
    def parse_while(self) -> N.WhileStatement:
        first = self.advance()
        self.expect_delim("(", "condition of 'while'")
        cond = self.parse_expression()
        self.expect_delim(")", "end of 'while' condition")
        body = self.parse_statement()
        n = N.WhileStatement(condition=cond, body=body)
        n.span = _span(first, self.prev())
        return n

    @rule("forStmt")
    def parse_for(self) -> N.ForStatement:
        first = self.advance()
        self.expect_delim("(", "'for' header")
        init = cond = update = None
        if not self.is_delim(";"):
            if self.is_type_kw():
                init = self.parse_var_decl()
            elif self.peek().type == TokenType.IDENTIFIER:
                init = self._for_simple()
            else:
                raise self.error("declaration, assignment or ';' in 'for' initializer")
        self.expect_delim(";", "after 'for' initializer")
        if not self.is_delim(";"):
            cond = self.parse_expression()
        self.expect_delim(";", "after 'for' condition")
        if not self.is_delim(")"):
            if self.peek().type != TokenType.IDENTIFIER:
                raise self.error("assignment or increment in 'for' update")
            update = self._for_simple()
        self.expect_delim(")", "end of 'for' header")
        body = self.parse_statement()
        n = N.ForStatement(init=init, condition=cond, update=update, body=body)
        n.span = _span(first, self.prev())
        return n

    def _for_simple(self) -> N.Node:
        nxt = self.peek(1)
        if nxt.type == TokenType.OPERATOR and nxt.lexeme in ASSIGN_OPS:
            return self._assignment()
        if nxt.type == TokenType.OPERATOR and nxt.lexeme in ("++", "--"):
            return self._incdec()
        self.advance()
        raise self.error("assignment, '++' or '--'")

    @rule("returnStmt")
    def parse_return(self) -> N.ReturnStatement:
        first = self.advance()
        value = None
        if not self.is_delim(";"):
            value = self.parse_expression()
        self.expect_delim(";", "end of 'return'")
        n = N.ReturnStatement(value=value)
        n.span = _span(first, self.prev())
        return n

    @rule("printStmt")
    def parse_print(self) -> N.PrintStatement:
        first = self.advance()
        self.expect_delim("(", "'print' takes one parenthesised expression")
        value = self.parse_expression()
        self.expect_delim(")", "end of 'print' argument")
        self.expect_delim(";", "end of 'print'")
        n = N.PrintStatement(value=value)
        n.span = _span(first, self.prev())
        return n

    # ---- expressions (lowest to highest precedence) --------------------
    @rule("expression")
    def parse_expression(self) -> N.Node:
        return self.parse_logical_or()

    def _binary_level(self, sub, ops, rule_name):
        left = sub()
        while self.is_op(*ops):
            op = self.advance().lexeme
            right = sub()
            b = N.BinaryExpression(operator=op, left=left, right=right)
            b.span = _join(left.span, right.span)
            left = b
        return left

    @rule("logicalOr")
    def parse_logical_or(self):
        return self._binary_level(self.parse_logical_and, ("||",), "logicalOr")

    @rule("logicalAnd")
    def parse_logical_and(self):
        return self._binary_level(self.parse_equality, ("&&",), "logicalAnd")

    @rule("equality")
    def parse_equality(self):
        return self._binary_level(self.parse_relational, ("==", "!="), "equality")

    @rule("relational")
    def parse_relational(self):
        return self._binary_level(self.parse_additive, ("<", "<=", ">", ">="), "relational")

    @rule("additive")
    def parse_additive(self):
        return self._binary_level(self.parse_multiplicative, ("+", "-"), "additive")

    @rule("multiplicative")
    def parse_multiplicative(self):
        return self._binary_level(self.parse_unary, ("*", "/", "%"), "multiplicative")

    @rule("unary")
    def parse_unary(self):
        if self.is_op("-", "!"):
            tok = self.advance()
            operand = self.parse_unary()
            u = N.UnaryExpression(operator=tok.lexeme, operand=operand)
            u.span = _join(_span(tok, tok), operand.span)
            return u
        return self.parse_call_or_primary()

    def parse_call_or_primary(self):
        if self.peek().type == TokenType.IDENTIFIER and self.is_delim("(", k=1):
            return self.parse_call()
        return self.parse_primary()

    @rule("call")
    def parse_call(self) -> N.FunctionCall:
        name_tok = self.advance()
        self.expect_delim("(")
        args: List[N.Node] = []
        if not self.is_delim(")"):
            while True:
                args.append(self.parse_expression())
                if self.is_delim(","):
                    self.advance()
                    continue
                break
        self.expect_delim(")", "end of argument list")
        c = N.FunctionCall(name=name_tok.lexeme, args=args)
        c.name_span = _span(name_tok, name_tok)
        c.span = _span(name_tok, self.prev())
        return c

    @rule("primary")
    def parse_primary(self):
        t = self.peek()
        if t.type in (TokenType.INTEGER_LITERAL, TokenType.FLOAT_LITERAL,
                      TokenType.STRING_LITERAL, TokenType.BOOLEAN_LITERAL):
            self.advance()
            ltype = {TokenType.INTEGER_LITERAL: "int", TokenType.FLOAT_LITERAL: "float",
                     TokenType.STRING_LITERAL: "string", TokenType.BOOLEAN_LITERAL: "bool"}[t.type]
            lit = N.Literal(lit_type=ltype, value=t.value, raw=t.lexeme)
            lit.span = _span(t, t)
            return lit
        if t.type == TokenType.IDENTIFIER:
            self.advance()
            ident = N.Identifier(name=t.lexeme)
            ident.span = _span(t, t)
            return ident
        if t.type == TokenType.DELIMITER and t.lexeme == "(":
            self.advance()
            inner = self.parse_expression()
            self.expect_delim(")", "closing parenthesis")
            return inner  # grouping leaves no node of its own
        if t.type == TokenType.DELIMITER and t.lexeme in ("[", "]", "."):
            raise ParseError(f"Unexpected '{t.lexeme}' (arrays and member access are not part of the supported grammar)",
                             t, "expression")
        raise self.error("expression")


class _Abort(Exception):
    pass


def parse_tokens(tokens: List[Token]) -> ParseResult:
    p = Parser(tokens)
    try:
        return p.parse()
    except _Abort:
        # too many errors: report what we have
        return ParseResult(False, None, p.errors, len(p.toks), p.i, p.comments_skipped,
                           dict(p.rule_counts), p.trace, p.max_depth, 0.0, 0)
