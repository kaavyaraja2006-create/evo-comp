"""Three-address-code IR data model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from compiler.runtime import BINARY_OPS, COMPARE_OPS, UNARY_OPS

OP_SYMBOL = {
    "ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/", "MOD": "%",
    "SHL": "<<", "SHR": ">>", "LT": "<", "LE": "<=", "GT": ">", "GE": ">=",
    "EQ": "==", "NE": "!=",
}
COMMUTATIVE = ("ADD", "MUL", "EQ", "NE")
TERMINATORS = ("JMP", "CBR", "RET")
ALL_OPCODES = ("MOV",) + BINARY_OPS + UNARY_OPS + ("LABEL", "JMP", "CBR", "CALL", "RET", "PRINT")

# Abstract per-instruction cost model (documented in docs/EVOLUTION.md).
COST_WEIGHTS: Dict[str, int] = {
    "MOV": 1, "ADD": 1, "SUB": 1, "MUL": 3, "DIV": 8, "MOD": 8, "SHL": 1, "SHR": 1,
    "NEG": 1, "NOT": 1, "I2F": 1, "LT": 1, "LE": 1, "GT": 1, "GE": 1, "EQ": 1, "NE": 1,
    "JMP": 1, "CBR": 2, "CALL": 10, "RET": 2, "PRINT": 5, "LABEL": 0,
}


@dataclass(frozen=True)
class Operand:
    kind: str                      # temp | var | global | const
    name: Optional[str] = None
    value: Any = None
    type: str = "int"

    @staticmethod
    def const(value: Any, type_: str) -> "Operand":
        return Operand("const", None, value, type_)

    def is_local(self) -> bool:
        return self.kind in ("temp", "var")

    def is_const(self) -> bool:
        return self.kind == "const"

    def key(self):
        if self.kind == "const":
            return ("const", self.type, repr(self.value))
        return (self.kind, self.name)

    def text(self) -> str:
        if self.kind == "const":
            v = self.value
            if self.type == "string":
                return json.dumps(v)
            if self.type == "bool":
                return "true" if v else "false"
            return repr(v)
        if self.kind == "global":
            return f"@{self.name}"
        return str(self.name)

    def to_dict(self) -> dict:
        d = {"kind": self.kind, "type": self.type, "text": self.text()}
        if self.kind == "const":
            d["value"] = self.value
        else:
            d["name"] = self.name
        return d


@dataclass
class Instr:
    id: int
    op: str
    dest: Optional[Operand] = None
    a: Optional[Operand] = None
    b: Optional[Operand] = None
    args: List[Operand] = field(default_factory=list)
    label: Optional[str] = None       # LABEL name, JMP target, CBR true-target
    label2: Optional[str] = None      # CBR false-target
    func: Optional[str] = None        # CALL target
    ty: Optional[str] = None          # operand type of the operation
    src: Optional[dict] = None        # originating AST node {nodeId,line,column}
    origins: List[int] = field(default_factory=list)  # ids in the *unoptimised* IR

    def clone(self, **changes) -> "Instr":
        d = dict(id=self.id, op=self.op, dest=self.dest, a=self.a, b=self.b, args=list(self.args),
                 label=self.label, label2=self.label2, func=self.func, ty=self.ty,
                 src=self.src, origins=list(self.origins))
        d.update(changes)
        return Instr(**d)

    # -- dataflow helpers -------------------------------------------------
    def defs(self) -> List[str]:
        if self.dest is not None and self.dest.is_local():
            return [self.dest.name]  # type: ignore[list-item]
        return []

    def operands_read(self) -> List[Operand]:
        ops: List[Operand] = []
        if self.a is not None:
            ops.append(self.a)
        if self.b is not None:
            ops.append(self.b)
        ops.extend(self.args)
        return ops

    def uses(self) -> List[str]:
        return [o.name for o in self.operands_read() if o.is_local()]  # type: ignore[misc]

    def labels_referenced(self) -> List[str]:
        if self.op == "JMP":
            return [self.label]  # type: ignore[list-item]
        if self.op == "CBR":
            return [self.label, self.label2]  # type: ignore[list-item]
        return []

    def text(self) -> str:
        op = self.op
        if op == "LABEL":
            return f"{self.label}:"
        if op == "JMP":
            return f"goto {self.label}"
        if op == "CBR":
            return f"if {self.a.text()} goto {self.label} else {self.label2}"  # type: ignore[union-attr]
        if op == "RET":
            return f"return {self.a.text()}" if self.a is not None else "return"
        if op == "PRINT":
            return f"print {self.a.text()}"  # type: ignore[union-attr]
        if op == "CALL":
            call = f"call {self.func}({', '.join(a.text() for a in self.args)})"
            return f"{self.dest.text()} = {call}" if self.dest is not None else call  # type: ignore[union-attr]
        d = self.dest.text() if self.dest is not None else "?"
        if op == "MOV":
            return f"{d} = {self.a.text()}"  # type: ignore[union-attr]
        if op == "NEG":
            return f"{d} = -{self.a.text()}"  # type: ignore[union-attr]
        if op == "NOT":
            return f"{d} = !{self.a.text()}"  # type: ignore[union-attr]
        if op == "I2F":
            return f"{d} = float({self.a.text()})"  # type: ignore[union-attr]
        return f"{d} = {self.a.text()} {OP_SYMBOL[op]} {self.b.text()}"  # type: ignore[union-attr]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "opcode": self.op, "text": self.text(), "type": self.ty,
            "dest": self.dest.to_dict() if self.dest else None,
            "arg1": self.a.to_dict() if self.a else None,
            "arg2": self.b.to_dict() if self.b else None,
            "args": [a.to_dict() for a in self.args],
            "label": self.label, "falseLabel": self.label2, "func": self.func,
            "src": self.src, "origins": self.origins,
        }


@dataclass
class IRFunction:
    name: str
    params: List[Operand]
    return_type: str
    instrs: List[Instr] = field(default_factory=list)
    synthetic: bool = False

    def real_instr_count(self) -> int:
        return sum(1 for i in self.instrs if i.op != "LABEL")

    def to_dict(self) -> dict:
        return {
            "name": self.name, "synthetic": self.synthetic, "returnType": self.return_type,
            "params": [{"name": p.name, "type": p.type} for p in self.params],
            "instructions": [i.to_dict() for i in self.instrs],
            "instructionCount": self.real_instr_count(),
        }


@dataclass
class IRProgram:
    functions: List[IRFunction]
    globals: List[Dict[str, str]]
    entry: str = "__start"

    def fn(self, name: str) -> IRFunction:
        for f in self.functions:
            if f.name == name:
                return f
        raise KeyError(name)

    def instr_count(self) -> int:
        return sum(f.real_instr_count() for f in self.functions)

    def all_instrs(self):
        for f in self.functions:
            for i in f.instrs:
                yield f, i

    def renumber(self) -> None:
        n = 1
        for f in self.functions:
            for i in f.instrs:
                i.id = n
                n += 1

    def text(self) -> str:
        lines: List[str] = []
        for f in self.functions:
            params = ", ".join(f"{p.type} {p.name}" for p in f.params)
            lines.append(f"function {f.name}({params}) -> {f.return_type}")
            for i in f.instrs:
                if i.op == "LABEL":
                    lines.append(f"  {i.text()}")
                else:
                    lines.append(f"    {i.id:>3}  {i.text()}")
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "entry": self.entry, "globals": self.globals,
            "functions": [f.to_dict() for f in self.functions],
            "instructionCount": self.instr_count(),
        }

    def compact(self) -> dict:
        """Small serialisation used for candidate IR pools."""
        return {"functions": [{"name": f.name, "instructions": [
            {"id": i.id, "text": i.text(), "op": i.op, "origins": i.origins} for i in f.instrs]}
            for f in self.functions]}
