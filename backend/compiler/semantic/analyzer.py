"""Semantic analysis for EvoLang: scopes, symbol table, type checking.

Input is the real AST. Output is a symbol table, per-expression types
(used by IR generation), and diagnostics. Nothing is hardcoded: every symbol
and diagnostic is derived from the tree being analysed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from compiler.ast import nodes as N
from compiler.ast.builder import ASTResult
from compiler.runtime import INT_MAX, INT_MIN

NUMERIC = ("int", "float")


@dataclass
class Symbol:
    id: int
    name: str
    type: str                     # variable/param type, or function return type
    kind: str                     # variable | parameter | function
    scope_id: int
    scope_name: str
    line: int
    column: int
    decl_node: int
    is_global: bool = False
    uses: List[dict] = field(default_factory=list)
    params: List[Tuple[str, str]] = field(default_factory=list)
    return_inferred: bool = False
    fn_node: Optional[N.FunctionDeclaration] = None
    analyzed: bool = False
    in_progress: bool = False
    call_count: int = 0

    def reads(self) -> int:
        return sum(1 for u in self.uses if u["access"] in ("read", "call"))

    def to_dict(self) -> dict:
        d = {
            "id": self.id, "name": self.name, "type": self.type, "kind": self.kind,
            "scope": self.scope_name, "scopeId": self.scope_id, "isGlobal": self.is_global,
            "declaration": {"line": self.line, "column": self.column, "nodeId": self.decl_node},
            "uses": self.uses, "useCount": len(self.uses),
        }
        if self.kind == "function":
            d["parameters"] = [{"name": n, "type": t} for n, t in self.params]
            d["returnType"] = self.type
            d["returnTypeInferred"] = self.return_inferred
        return d


@dataclass
class Scope:
    id: int
    name: str
    kind: str                     # global | function | block | for | branch
    parent: Optional["Scope"]
    symbols: Dict[str, Symbol] = field(default_factory=dict)
    order: List[Symbol] = field(default_factory=list)
    child_counter: Dict[str, int] = field(default_factory=dict)
    closed: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind,
                "parent": self.parent.id if self.parent else None,
                "symbols": [s.id for s in self.order]}


@dataclass
class FnCtx:
    sym: Symbol
    inferred: Optional[str] = None
    saw_value_return: bool = False
    saw_void_return: bool = False


@dataclass
class SemanticResult:
    success: bool
    diagnostics: List[dict]
    symbols: List[Symbol]
    scopes: List[Scope]
    types: Dict[int, str]
    resolutions: Dict[int, int]
    functions: Dict[str, Symbol]
    symbols_by_id: Dict[int, Symbol]
    implicit_conversions: int
    analyze_ms: float

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d["severity"] == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d["severity"] == "warning")

    def to_dict(self) -> dict:
        kinds: Dict[str, int] = {}
        for s in self.symbols:
            kinds[s.kind] = kinds.get(s.kind, 0) + 1
        return {
            "success": self.success,
            "status": "VALID" if self.success else "INVALID",
            "errorCount": self.error_count,
            "warningCount": self.warning_count,
            "diagnostics": self.diagnostics,
            "symbols": [s.to_dict() for s in self.symbols],
            "scopes": [s.to_dict() for s in self.scopes],
            "nodeTypes": {str(k): v for k, v in self.types.items()},
            "statistics": {
                "symbolCount": len(self.symbols), "byKind": kinds,
                "scopeCount": len(self.scopes),
                "typedExpressions": len(self.types),
                "implicitConversions": self.implicit_conversions,
            },
            "analyzeMs": round(self.analyze_ms, 4),
        }


class SemanticAnalyzer:
    def __init__(self, ast: ASTResult):
        self.ast = ast
        self.diags: List[dict] = []
        self.symbols: List[Symbol] = []
        self.scopes: List[Scope] = []
        self.types: Dict[int, str] = {}
        self.res: Dict[int, int] = {}
        self.closed_by_name: Dict[str, List[Symbol]] = {}
        self.implicit = 0
        self.global_scope = self._new_scope("global", "global", None)
        self.scope = self.global_scope
        self.fn: Optional[FnCtx] = None
        self.functions: Dict[str, Symbol] = {}

    # ---- utilities ----------------------------------------------------
    def _new_scope(self, name: str, kind: str, parent: Optional[Scope]) -> Scope:
        s = Scope(len(self.scopes), name, kind, parent)
        self.scopes.append(s)
        return s

    def diag(self, severity: str, code: str, msg: str, node: N.Node, symbol: Optional[str] = None,
             span: Optional[N.Span] = None):
        sp = span or node.span
        self.diags.append({"severity": severity, "code": code, "message": msg,
                           "line": sp.line, "column": sp.column, "symbol": symbol, "nodeId": node.id})

    def error(self, code, msg, node, symbol=None, span=None):
        self.diag("error", code, msg, node, symbol, span)

    def warn(self, code, msg, node, symbol=None, span=None):
        self.diag("warning", code, msg, node, symbol, span)

    def push_scope(self, kind: str) -> Scope:
        parent = self.scope
        n = parent.child_counter.get(kind, 0) + 1
        parent.child_counter[kind] = n
        s = self._new_scope(f"{parent.name}.{kind}{n}", kind, parent)
        self.scope = s
        return s

    def pop_scope(self):
        s = self.scope
        s.closed = True
        for sym in s.order:
            self.closed_by_name.setdefault(sym.name, []).append(sym)
        self.scope = s.parent  # type: ignore

    def declare(self, name, type_, kind, node: N.Node, span: Optional[N.Span] = None) -> Optional[Symbol]:
        sp = span or node.span
        existing = self.scope.symbols.get(name)
        if existing is not None:
            what = "function" if existing.kind == "function" else existing.kind
            self.error("E002", f"Duplicate declaration of '{name}' (already declared as {what} "
                               f"at line {existing.line}, column {existing.column})", node, name, sp)
            return None
        # shadowing warning
        outer = self.scope.parent
        while outer is not None:
            o = outer.symbols.get(name)
            if o is not None and o.kind in ("variable", "parameter") and kind != "function":
                self.warn("W004", f"'{name}' shadows the {o.kind} declared at line {o.line}", node, name, sp)
                break
            outer = outer.parent
        sym = Symbol(len(self.symbols), name, type_, kind, self.scope.id, self.scope.name,
                     sp.line, sp.column, node.id, is_global=(self.scope.kind == "global"))
        self.symbols.append(sym)
        self.scope.symbols[name] = sym
        self.scope.order.append(sym)
        return sym

    def lookup(self, name: str) -> Optional[Symbol]:
        s: Optional[Scope] = self.scope
        while s is not None:
            if name in s.symbols:
                return s.symbols[name]
            s = s.parent
        return None

    def use(self, sym: Symbol, node: N.Node, access: str, span: Optional[N.Span] = None):
        sp = span or node.span
        sym.uses.append({"line": sp.line, "column": sp.column, "nodeId": node.id, "access": access})
        self.res[node.id] = sym.id

    @staticmethod
    def assignable(target: str, src: str) -> bool:
        return target == src or (target == "float" and src == "int") or "error" in (target, src)

    def coerced(self, target: str, src: str):
        if target == "float" and src == "int":
            self.implicit += 1

    # ---- entry ---------------------------------------------------------
    def analyze(self) -> SemanticResult:
        t0 = time.perf_counter()
        prog = self.ast.root
        # Pass 1: register function signatures so calls may precede definitions.
        for item in prog.body:
            if isinstance(item, N.FunctionDeclaration):
                self._register_function(item)
        # Pass 2: analyse in source order.
        for item in prog.body:
            if isinstance(item, N.FunctionDeclaration):
                sym = self.global_scope.symbols.get(item.name)
                if sym is not None and sym.fn_node is item:
                    self.analyze_function(sym)
            else:
                self.stmt(item)
        self.global_scope.closed = True
        # main signature
        m = self.functions.get("main")
        if m is not None and m.params:
            self.error("E014", "Function 'main' must take no parameters", m.fn_node, "main",
                       m.fn_node.span)  # type: ignore[arg-type]
        # unused variables (after all uses, including uses inside later functions)
        for s in self.symbols:
            if s.kind == "variable" and s.reads() == 0:
                self.warn("W001", f"Variable '{s.name}' is declared but never read",
                          self.ast.nodes[s.decl_node], s.name,
                          N.Span(s.line, s.column))
        self.diags.sort(key=lambda d: (d["line"], d["column"], 0 if d["severity"] == "error" else 1, d["code"]))
        ms = (time.perf_counter() - t0) * 1000
        return SemanticResult(
            success=not any(d["severity"] == "error" for d in self.diags),
            diagnostics=self.diags, symbols=self.symbols, scopes=self.scopes,
            types=self.types, resolutions=self.res, functions=self.functions,
            symbols_by_id={s.id: s for s in self.symbols},
            implicit_conversions=self.implicit, analyze_ms=ms,
        )

    def _register_function(self, fn: N.FunctionDeclaration):
        sp = fn.span
        name_span = N.Span(sp.line, sp.column + (len("function ") if fn.form == "function"
                                                else len(fn.return_type or "") + 1))
        sym = self.declare(fn.name, fn.return_type or "void", "function", fn, name_span)
        if sym is None:
            return
        sym.params = [(p.name, p.type) for p in fn.params]
        sym.fn_node = fn
        sym.return_inferred = fn.return_type is None
        self.functions[fn.name] = sym

    # ---- functions -----------------------------------------------------
    def analyze_function(self, sym: Symbol):
        if sym.analyzed or sym.in_progress:
            return
        sym.in_progress = True
        saved = (self.scope, self.fn)
        fn = sym.fn_node
        assert fn is not None
        self.scope = self.global_scope
        fscope = self._new_scope(fn.name, "function", self.global_scope)
        self.scope = fscope
        self.fn = FnCtx(sym)
        for p in fn.params:
            self.declare(p.name, p.type, "parameter", p)
        self.stmts(fn.body.statements)  # type: ignore[union-attr]
        ctx = self.fn
        if sym.return_inferred:
            sym.type = ctx.inferred or "void"
        if sym.type != "void" and fn.name != "main" and not self.always_returns(fn.body):
            self.warn("W003", f"Function '{fn.name}' may reach its end without returning a value "
                              f"(a default {sym.type} value is returned)", fn, fn.name,
                      N.Span(fn.span.line, fn.span.column))
        self.pop_scope()
        sym.analyzed = True
        sym.in_progress = False
        self.scope, self.fn = saved

    def always_returns(self, s: Optional[N.Node]) -> bool:
        if s is None:
            return False
        if isinstance(s, N.ReturnStatement):
            return True
        if isinstance(s, N.BlockStatement):
            return any(self.always_returns(x) for x in s.statements)
        if isinstance(s, N.IfStatement):
            return s.else_branch is not None and self.always_returns(s.then_branch) \
                and self.always_returns(s.else_branch)
        if isinstance(s, N.WhileStatement):
            c = s.condition
            return isinstance(c, N.Literal) and c.value is True
        if isinstance(s, N.ForStatement):
            return s.condition is None
        return False

    # ---- statements ----------------------------------------------------
    def stmts(self, lst: List[N.Node]):
        warned = False
        returned = False
        for s in lst:
            if returned and not warned:
                self.warn("W002", "Unreachable code after 'return'", s)
                warned = True
            self.stmt(s)
            if isinstance(s, N.ReturnStatement):
                returned = True

    def scoped_stmt(self, s: Optional[N.Node], kind: str = "branch"):
        if s is None:
            return
        if isinstance(s, N.BlockStatement):
            self.stmt(s)
        else:
            self.push_scope(kind)
            self.stmt(s)
            self.pop_scope()

    def stmt(self, s: N.Node):
        if isinstance(s, N.VariableDeclaration):
            self.var_decl(s)
        elif isinstance(s, N.Assignment):
            self.assignment(s)
        elif isinstance(s, N.IncDecStatement):
            self.incdec(s)
        elif isinstance(s, N.IfStatement):
            self.cond(s.condition, "if")
            self.scoped_stmt(s.then_branch)
            self.scoped_stmt(s.else_branch)
        elif isinstance(s, N.WhileStatement):
            self.cond(s.condition, "while")
            self.scoped_stmt(s.body)
        elif isinstance(s, N.ForStatement):
            self.push_scope("for")
            if s.init is not None:
                self.stmt(s.init)
            if s.condition is not None:
                self.cond(s.condition, "for")
            if s.update is not None:
                self.stmt(s.update)
            self.scoped_stmt(s.body)
            self.pop_scope()
        elif isinstance(s, N.ReturnStatement):
            self.return_stmt(s)
        elif isinstance(s, N.PrintStatement):
            self.value_expr(s.value)  # type: ignore[arg-type]
        elif isinstance(s, N.ExpressionStatement):
            self.expr(s.expression)  # type: ignore[arg-type]
        elif isinstance(s, N.BlockStatement):
            self.push_scope("block")
            self.stmts(s.statements)
            self.pop_scope()
        else:  # FunctionDeclaration nested: parser forbids
            self.error("E000", f"Unsupported statement {s.node_type}", s)

    def var_decl(self, d: N.VariableDeclaration):
        init_t = None
        if d.init is not None:
            init_t = self.value_expr(d.init)  # analysed before the name is in scope
        sym = self.declare(d.name, d.var_type, "variable", d,
                           N.Span(d.span.line, d.span.column + len(d.var_type) + 1))
        if init_t is not None and not self.assignable(d.var_type, init_t):
            self.type_mismatch(d, d.var_type, init_t, d.name, initializing=True)
        elif init_t is not None:
            self.coerced(d.var_type, init_t)
        if sym is not None:
            self.types[d.id] = d.var_type

    def type_mismatch(self, node, target, src, name, initializing=False):
        verb = "initialize" if initializing else "assign to"
        if target == "int" and src == "float":
            self.error("E003", f"Cannot {verb} 'int' variable '{name}' with 'float' (narrowing conversion "
                               f"is not implicit)", node, name)
        else:
            self.error("E003", f"Cannot {verb} '{target}' variable '{name}' with a value of type '{src}'",
                       node, name)

    def target_symbol(self, ident: N.Identifier, access: str) -> Optional[Symbol]:
        sym = self.lookup(ident.name)
        if sym is None:
            self.undeclared(ident)
            return None
        if sym.kind == "function":
            self.error("E005", f"Cannot assign to '{ident.name}': it is a function", ident, ident.name)
            return None
        self.use(sym, ident, access)
        self.types[ident.id] = sym.type
        return sym

    def assignment(self, a: N.Assignment):
        vt = self.value_expr(a.value)  # type: ignore[arg-type]
        access = "write" if a.operator == "=" else "readwrite"
        sym = self.target_symbol(a.target, access)  # type: ignore[arg-type]
        if sym is None:
            return
        if a.operator == "=":
            if not self.assignable(sym.type, vt):
                self.type_mismatch(a, sym.type, vt, sym.name)
            else:
                self.coerced(sym.type, vt)
            return
        op = a.operator[0]
        rt = self.binary_result(op, sym.type, vt, a, a.value)  # type: ignore[arg-type]
        if rt != "error" and not self.assignable(sym.type, rt):
            self.error("E003", f"Cannot store '{rt}' result of '{a.operator}' into '{sym.type}' "
                               f"variable '{sym.name}'", a, sym.name)

    def incdec(self, s: N.IncDecStatement):
        sym = self.target_symbol(s.target, "readwrite")  # type: ignore[arg-type]
        if sym is not None and sym.type not in NUMERIC:
            self.error("E016", f"Operator '{s.operator}' requires an int or float variable, "
                               f"but '{sym.name}' is '{sym.type}'", s, sym.name)

    def cond(self, e: Optional[N.Node], what: str):
        t = self.value_expr(e)  # type: ignore[arg-type]
        if t not in ("bool", "error"):
            self.error("E010", f"Condition of '{what}' must be of type bool, found '{t}'", e)  # type: ignore[arg-type]

    def return_stmt(self, r: N.ReturnStatement):
        if self.fn is None:
            self.error("E009", "'return' outside of a function", r)
            if r.value is not None:
                self.value_expr(r.value)
            return
        fn = self.fn
        sym = fn.sym
        if r.value is None:
            if sym.return_inferred:
                if fn.saw_value_return:
                    self.error("E009", f"'return' without a value, but '{sym.name}' "
                                       f"already returns '{fn.inferred}' elsewhere", r, sym.name)
                fn.saw_void_return = True
            elif sym.type != "void":
                self.error("E009", f"'return' without a value in function '{sym.name}' declared to "
                                   f"return '{sym.type}'", r, sym.name)
            return
        t = self.value_expr(r.value)
        if sym.return_inferred:
            if fn.saw_void_return:
                self.error("E009", f"Function '{sym.name}' returns a value here but returns nothing elsewhere",
                           r, sym.name)
            fn.saw_value_return = True
            if t == "error":
                return
            if fn.inferred is None:
                fn.inferred = t
            elif fn.inferred != t:
                if fn.inferred in NUMERIC and t in NUMERIC:
                    fn.inferred = "float"
                    self.implicit += 1
                else:
                    self.error("E009", f"Inconsistent return types in '{sym.name}': '{fn.inferred}' and '{t}'",
                               r, sym.name)
            return
        if sym.type == "void":
            self.error("E009", f"Function '{sym.name}' returns no value but 'return' has a value", r, sym.name)
        elif not self.assignable(sym.type, t):
            self.error("E009", f"Cannot return '{t}' from function '{sym.name}' declared to return "
                               f"'{sym.type}'", r, sym.name)
        else:
            self.coerced(sym.type, t)

    # ---- expressions ---------------------------------------------------
    def undeclared(self, ident: N.Identifier):
        note = ""
        gone = self.closed_by_name.get(ident.name)
        if gone:
            g = gone[-1]
            note = (f" (a {g.kind} named '{ident.name}' exists in scope '{g.scope_name}', "
                    f"declared at line {g.line}, but is not visible here)")
        self.error("E001", f"Undeclared identifier '{ident.name}'{note}", ident, ident.name)
        self.types[ident.id] = "error"

    def value_expr(self, e: N.Node) -> str:
        t = self.expr(e)
        if t == "void":
            name = e.name if isinstance(e, N.FunctionCall) else "expression"
            self.error("E012", f"'{name}' returns no value, so it cannot be used as a value", e, name)
            self.types[e.id] = "error"
            return "error"
        return t

    def expr(self, e: N.Node) -> str:
        t = self._expr(e)
        self.types[e.id] = t
        return t

    def _expr(self, e: N.Node) -> str:
        if isinstance(e, N.Literal):
            if e.lit_type == "int" and not (INT_MIN <= e.value <= INT_MAX):
                self.error("E013", f"Integer literal {e.raw} is out of range for 32-bit int", e)
                return "error"
            return e.lit_type
        if isinstance(e, N.Identifier):
            sym = self.lookup(e.name)
            if sym is None:
                self.undeclared(e)
                return "error"
            if sym.kind == "function":
                self.error("E006", f"'{e.name}' is a function; call it with parentheses to use its value",
                           e, e.name)
                self.use(sym, e, "read")
                return "error"
            self.use(sym, e, "read")
            return sym.type
        if isinstance(e, N.FunctionCall):
            return self.call(e)
        if isinstance(e, N.UnaryExpression):
            t = self.value_expr(e.operand)  # type: ignore[arg-type]
            if t == "error":
                return "error" if e.operator == "-" else "bool"
            if e.operator == "-":
                if t in NUMERIC:
                    return t
                self.error("E004", f"Operator '-' cannot be applied to '{t}'", e)
                return "error"
            if t == "bool":
                return "bool"
            self.error("E004", f"Operator '!' requires a bool operand, found '{t}'", e)
            return "bool"
        if isinstance(e, N.BinaryExpression):
            lt = self.value_expr(e.left)  # type: ignore[arg-type]
            rt = self.value_expr(e.right)  # type: ignore[arg-type]
            return self.binary_result(e.operator, lt, rt, e, e.right)  # type: ignore[arg-type]
        self.error("E000", f"Unsupported expression {e.node_type}", e)
        return "error"

    def binary_result(self, op: str, lt: str, rt: str, node: N.Node, right: N.Node) -> str:
        bool_result = op in ("<", "<=", ">", ">=", "==", "!=", "&&", "||")
        if op in ("/", "%") and isinstance(right, N.Literal) and right.lit_type in NUMERIC and right.value == 0:
            self.error("E011", "Division by zero (the divisor is the constant 0)", node)
        if "error" in (lt, rt):
            return "bool" if bool_result else "error"
        if op in ("+", "-", "*", "/"):
            if lt in NUMERIC and rt in NUMERIC:
                if lt != rt:
                    self.implicit += 1
                return "float" if "float" in (lt, rt) else "int"
            if op == "+" and lt == "string" and rt == "string":
                return "string"
            self.error("E004", f"Operator '{op}' cannot be applied to '{lt}' and '{rt}'", node)
            return "error"
        if op == "%":
            if lt == "int" and rt == "int":
                return "int"
            self.error("E004", f"Operator '%' requires int operands, found '{lt}' and '{rt}'", node)
            return "error"
        if op in ("<", "<=", ">", ">="):
            if lt in NUMERIC and rt in NUMERIC:
                if lt != rt:
                    self.implicit += 1
                return "bool"
            self.error("E004", f"Operator '{op}' requires numeric operands, found '{lt}' and '{rt}'", node)
            return "bool"
        if op in ("==", "!="):
            if (lt in NUMERIC and rt in NUMERIC) or lt == rt:
                if lt != rt:
                    self.implicit += 1
                return "bool"
            self.error("E004", f"Operator '{op}' cannot compare '{lt}' with '{rt}'", node)
            return "bool"
        if op in ("&&", "||"):
            if lt == "bool" and rt == "bool":
                return "bool"
            self.error("E004", f"Operator '{op}' requires bool operands, found '{lt}' and '{rt}'", node)
            return "bool"
        self.error("E004", f"Unknown operator '{op}'", node)
        return "error"

    def call(self, c: N.FunctionCall) -> str:
        sym = self.lookup(c.name)
        arg_types = [self.value_expr(a) for a in c.args]
        if sym is None:
            self.error("E006", f"Call to undeclared function '{c.name}'", c, c.name, c.name_span)
            return "error"
        if sym.kind != "function":
            self.error("E006", f"'{c.name}' is a {sym.kind}, not a function", c, c.name, c.name_span)
            self.use(sym, c, "read", c.name_span)
            return "error"
        self.use(sym, c, "call", c.name_span)
        sym.call_count += 1
        if len(arg_types) != len(sym.params):
            self.error("E007", f"Function '{c.name}' expects {len(sym.params)} argument(s) but "
                               f"{len(arg_types)} were provided", c, c.name, c.name_span)
        else:
            for i, ((pname, ptype), at) in enumerate(zip(sym.params, arg_types)):
                if not self.assignable(ptype, at):
                    self.error("E008", f"Argument {i + 1} of '{c.name}' ('{pname}') expects '{ptype}' "
                                       f"but got '{at}'", c.args[i], c.name)
                else:
                    self.coerced(ptype, at)
        if sym.return_inferred and not sym.analyzed:
            if sym.in_progress:
                self.error("E015", f"Cannot infer the return type of '{c.name}' because it calls itself; "
                                   f"declare it with an explicit type, e.g. 'int {c.name}(...)'",
                           c, c.name, c.name_span)
                return "error"
            self.analyze_function(sym)
        return sym.type


def analyze(ast: ASTResult) -> SemanticResult:
    return SemanticAnalyzer(ast).analyze()
