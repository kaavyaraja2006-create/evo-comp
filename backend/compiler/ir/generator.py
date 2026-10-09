"""AST -> three-address IR.

Consumes the real AST and the semantic analyser's types/resolutions. Every
instruction records the AST node it came from (``src``), which is what makes
IR -> source traceability possible.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from compiler.ast import nodes as N
from compiler.ast.builder import ASTResult
from compiler.runtime import default_value
from compiler.semantic.analyzer import SemanticResult, Symbol
from .instructions import Instr, IRFunction, IRProgram, Operand

ARITH = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD"}
CMP = {"<": "LT", "<=": "LE", ">": "GT", ">=": "GE", "==": "EQ", "!=": "NE"}


class _FB:
    """Per-function builder state."""

    def __init__(self, name: str):
        self.name = name
        self.instrs: List[Instr] = []
        self.temps = 0
        self.labels = 0
        self.names: Dict[int, str] = {}
        self.used_names: Dict[str, int] = {}


class IRGenerator:
    def __init__(self, ast: ASTResult, sem: SemanticResult):
        self.ast = ast
        self.sem = sem
        self.next_id = 1
        self.fb: _FB = None  # type: ignore[assignment]
        self.cur: Optional[N.Node] = None

    # ---- emit helpers -------------------------------------------------
    def emit(self, op: str, **kw) -> Instr:
        node = self.cur
        src = None
        if node is not None:
            src = {"nodeId": node.id, "line": node.span.line, "column": node.span.column}
        ins = Instr(id=self.next_id, op=op, src=src, **kw)
        ins.origins = [ins.id]
        self.next_id += 1
        self.fb.instrs.append(ins)
        return ins

    def temp(self, type_: str) -> Operand:
        self.fb.temps += 1
        return Operand("temp", f"t{self.fb.temps}", None, type_)

    def label(self) -> str:
        self.fb.labels += 1
        return f"L{self.fb.labels}"

    def place(self, lbl: str):
        self.emit("LABEL", label=lbl)

    def var_operand(self, sym: Symbol) -> Operand:
        if sym.is_global:
            return Operand("global", sym.name, None, sym.type)
        fb = self.fb
        if sym.id not in fb.names:
            base = sym.name
            k = fb.used_names.get(base, 0)
            fb.used_names[base] = k + 1
            fb.names[sym.id] = base if k == 0 else f"{base}.{k}"
        return Operand("var", fb.names[sym.id], None, sym.type)

    def coerce(self, op: Operand, src: str, dst: str) -> Operand:
        if src == "int" and dst == "float":
            if op.is_const():
                return Operand.const(float(op.value), "float")
            t = self.temp("float")
            self.emit("I2F", dest=t, a=op, ty="int")
            return t
        return op

    # ---- program --------------------------------------------------------
    def generate(self) -> IRProgram:
        funcs: List[IRFunction] = []
        prog = self.ast.root
        for item in prog.body:
            if isinstance(item, N.FunctionDeclaration):
                funcs.append(self.gen_function(item))
        funcs.append(self.gen_start(prog))
        # __start goes first so the entry point reads top-down
        funcs.insert(0, funcs.pop())
        globals_ = [{"name": s.name, "type": s.type} for s in self.sem.symbols
                    if s.is_global and s.kind == "variable"]
        return IRProgram(funcs, globals_)

    def gen_start(self, prog: N.Program) -> IRFunction:
        self.fb = _FB("__start")
        self.cur = prog
        for item in prog.body:
            if not isinstance(item, N.FunctionDeclaration):
                self.stmt(item)
        self.cur = prog
        main = self.sem.functions.get("main")
        if main is not None:
            if main.type != "void":
                t = self.temp(main.type)
                self.emit("CALL", dest=t, func="main", args=[])
                self.emit("RET", a=t)
                rtype = main.type
            else:
                self.emit("CALL", func="main", args=[])
                self.emit("RET")
                rtype = "void"
        else:
            self.emit("RET")
            rtype = "void"
        return IRFunction("__start", [], rtype, self.fb.instrs, synthetic=True)

    def gen_function(self, fn: N.FunctionDeclaration) -> IRFunction:
        sym = self.sem.functions[fn.name]
        self.fb = _FB(fn.name)
        self.cur = fn
        params: List[Operand] = []
        for p in fn.params:
            self.fb.used_names[p.name] = self.fb.used_names.get(p.name, 0) + 1
            params.append(Operand("var", p.name, None, p.type))
        # map parameter symbols
        for s in self.sem.symbols:
            if s.kind == "parameter" and s.scope_name == fn.name:
                self.fb.names[s.id] = s.name
        self.stmts(fn.body.statements)  # type: ignore[union-attr]
        self.cur = fn
        if not self.fb.instrs or self.fb.instrs[-1].op != "RET":
            if sym.type == "void":
                self.emit("RET")
            else:
                self.emit("RET", a=Operand.const(default_value(sym.type), sym.type))
        return IRFunction(fn.name, params, sym.type, self.fb.instrs)

    # ---- statements -------------------------------------------------------
    def stmts(self, lst):
        for s in lst:
            self.stmt(s)

    def stmt(self, s: N.Node):
        self.cur = s
        if isinstance(s, N.VariableDeclaration):
            sym = self.decl_symbol(s)
            dest = self.var_operand(sym)
            if s.init is not None:
                v = self.expr(s.init)
                v = self.coerce(v, self.sem.types[s.init.id], s.var_type)
            else:
                v = Operand.const(default_value(s.var_type), s.var_type)
            self.cur = s
            self.emit("MOV", dest=dest, a=v, ty=s.var_type)
        elif isinstance(s, N.Assignment):
            self.assignment(s)
        elif isinstance(s, N.IncDecStatement):
            sym = self.sym_of(s.target)  # type: ignore[arg-type]
            one = Operand.const(1 if sym.type == "int" else 1.0, sym.type)
            self.update_var(sym, "ADD" if s.operator == "++" else "SUB", one, sym.type)
        elif isinstance(s, N.IfStatement):
            c = self.expr(s.condition)  # type: ignore[arg-type]
            self.cur = s
            lthen = self.label()
            lend = self.label()
            lelse = self.label() if s.else_branch is not None else lend
            self.emit("CBR", a=c, label=lthen, label2=lelse)
            self.place(lthen)
            self.stmt(s.then_branch)  # type: ignore[arg-type]
            if s.else_branch is not None:
                self.cur = s
                self.emit("JMP", label=lend)
                self.place(lelse)
                self.stmt(s.else_branch)
            self.cur = s
            self.place(lend)
        elif isinstance(s, N.WhileStatement):
            lcond, lbody, lend = self.label(), self.label(), self.label()
            self.place(lcond)
            c = self.expr(s.condition)  # type: ignore[arg-type]
            self.cur = s
            self.emit("CBR", a=c, label=lbody, label2=lend)
            self.place(lbody)
            self.stmt(s.body)  # type: ignore[arg-type]
            self.cur = s
            self.emit("JMP", label=lcond)
            self.place(lend)
        elif isinstance(s, N.ForStatement):
            if s.init is not None:
                self.stmt(s.init)
            self.cur = s
            lcond, lbody, lend = self.label(), self.label(), self.label()
            self.place(lcond)
            if s.condition is not None:
                c = self.expr(s.condition)
                self.cur = s
                self.emit("CBR", a=c, label=lbody, label2=lend)
            self.place(lbody)
            self.stmt(s.body)  # type: ignore[arg-type]
            if s.update is not None:
                self.stmt(s.update)
            self.cur = s
            self.emit("JMP", label=lcond)
            self.place(lend)
        elif isinstance(s, N.ReturnStatement):
            fn_sym = self.sem.functions[self.fb.name]
            if s.value is None:
                self.emit("RET")
            else:
                v = self.expr(s.value)
                v = self.coerce(v, self.sem.types[s.value.id], fn_sym.type)
                self.cur = s
                self.emit("RET", a=v)
        elif isinstance(s, N.PrintStatement):
            v = self.expr(s.value)  # type: ignore[arg-type]
            self.cur = s
            self.emit("PRINT", a=v, ty=self.sem.types[s.value.id])  # type: ignore[union-attr]
        elif isinstance(s, N.ExpressionStatement):
            self.expr(s.expression, discard=True)  # type: ignore[arg-type]
        elif isinstance(s, N.BlockStatement):
            self.stmts(s.statements)
        else:
            raise ValueError(f"IR generation: unsupported node {s.node_type}")

    def decl_symbol(self, d: N.VariableDeclaration) -> Symbol:
        if not hasattr(self, "_decl_map"):
            self._decl_map = {s.decl_node: s for s in self.sem.symbols if s.kind != "function"}
        return self._decl_map[d.id]

    def sym_of(self, ident: N.Identifier) -> Symbol:
        return self.sem.symbols_by_id[self.sem.resolutions[ident.id]]

    def update_var(self, sym: Symbol, op: str, rhs: Operand, ty: str):
        """var = var <op> rhs  (rhs already coerced to ty)."""
        if sym.is_global:
            cur = self.temp(sym.type)
            self.emit("MOV", dest=cur, a=self.var_operand(sym), ty=sym.type)
            res = self.temp(sym.type)
            self.emit(op, dest=res, a=cur, b=rhs, ty=ty)
            self.emit("MOV", dest=self.var_operand(sym), a=res, ty=sym.type)
        else:
            v = self.var_operand(sym)
            self.emit(op, dest=v, a=v, b=rhs, ty=ty)

    def assignment(self, s: N.Assignment):
        sym = self.sym_of(s.target)  # type: ignore[arg-type]
        v = self.expr(s.value)  # type: ignore[arg-type]
        vt = self.sem.types[s.value.id]  # type: ignore[union-attr]
        self.cur = s
        if s.operator == "=":
            v = self.coerce(v, vt, sym.type)
            self.cur = s
            self.emit("MOV", dest=self.var_operand(sym), a=v, ty=sym.type)
            return
        opc = ARITH[s.operator[0]]
        ty = sym.type
        v = self.coerce(v, vt, ty)
        self.cur = s
        self.update_var(sym, opc, v, ty)

    # ---- expressions --------------------------------------------------------
    def expr(self, e: N.Node, discard: bool = False) -> Optional[Operand]:
        prev = self.cur
        self.cur = e
        try:
            return self._expr(e, discard)
        finally:
            self.cur = prev

    def _expr(self, e: N.Node, discard: bool) -> Optional[Operand]:
        types = self.sem.types
        if isinstance(e, N.Literal):
            return Operand.const(e.value, e.lit_type)
        if isinstance(e, N.Identifier):
            sym = self.sym_of(e)
            if sym.is_global:
                t = self.temp(sym.type)
                self.emit("MOV", dest=t, a=self.var_operand(sym), ty=sym.type)
                return t
            return self.var_operand(sym)
        if isinstance(e, N.UnaryExpression):
            a = self.expr(e.operand)  # type: ignore[arg-type]
            self.cur = e
            t = self.temp(types[e.id])
            self.emit("NEG" if e.operator == "-" else "NOT", dest=t, a=a, ty=types[e.operand.id])  # type: ignore[union-attr]
            return t
        if isinstance(e, N.BinaryExpression):
            if e.operator in ("&&", "||"):
                return self.short_circuit(e)
            lt, rt = types[e.left.id], types[e.right.id]  # type: ignore[union-attr]
            a = self.expr(e.left)  # type: ignore[arg-type]
            b = self.expr(e.right)  # type: ignore[arg-type]
            common = "float" if "float" in (lt, rt) else lt
            a = self.coerce(a, lt, common)  # type: ignore[arg-type]
            b = self.coerce(b, rt, common)  # type: ignore[arg-type]
            self.cur = e
            opc = ARITH.get(e.operator) or CMP[e.operator]
            t = self.temp(types[e.id])
            self.emit(opc, dest=t, a=a, b=b, ty=common)
            return t
        if isinstance(e, N.FunctionCall):
            sym = self.sem.functions[e.name]
            args: List[Operand] = []
            for arg, (_, ptype) in zip(e.args, sym.params):
                v = self.expr(arg)
                args.append(self.coerce(v, types[arg.id], ptype))  # type: ignore[arg-type]
            self.cur = e
            dest = None
            if sym.type != "void" and not discard:
                dest = self.temp(sym.type)
            self.emit("CALL", dest=dest, func=e.name, args=args)
            return dest
        raise ValueError(f"IR generation: unsupported expression {e.node_type}")

    def short_circuit(self, e: N.BinaryExpression) -> Operand:
        t = self.temp("bool")
        a = self.expr(e.left)  # type: ignore[arg-type]
        self.cur = e
        self.emit("MOV", dest=t, a=a, ty="bool")
        lrhs, lend = self.label(), self.label()
        if e.operator == "&&":
            self.emit("CBR", a=t, label=lrhs, label2=lend)
        else:
            self.emit("CBR", a=t, label=lend, label2=lrhs)
        self.place(lrhs)
        b = self.expr(e.right)  # type: ignore[arg-type]
        self.cur = e
        self.emit("MOV", dest=t, a=b, ty="bool")
        self.place(lend)
        return t


def generate_ir(ast: ASTResult, sem: SemanticResult):
    t0 = time.perf_counter()
    prog = IRGenerator(ast, sem).generate()
    prog.renumber()  # ids follow display order: __start first, then functions
    for _, ins in prog.all_instrs():
        ins.origins = [ins.id]
    return prog, (time.perf_counter() - t0) * 1000
