"""EvoVM bytecode model and instruction-set definition."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# op -> (operand description, stack effect text, description)
ISA: Dict[str, tuple] = {
    "PUSH": ("constant", "+1", "Push a constant onto the stack."),
    "LOAD": ("local slot", "+1", "Push the value of a local variable slot."),
    "STORE": ("local slot", "-1", "Pop the top of the stack into a local variable slot."),
    "GLOAD": ("global name", "+1", "Push the value of a global variable."),
    "GSTORE": ("global name", "-1", "Pop the top of the stack into a global variable."),
    "ADD": ("-", "-2 +1", "Pop b, a; push a + b (int wraps to 32 bits; string concatenates)."),
    "SUB": ("-", "-2 +1", "Pop b, a; push a - b."),
    "MUL": ("-", "-2 +1", "Pop b, a; push a * b."),
    "DIV": ("-", "-2 +1", "Pop b, a; push a / b. Ints truncate toward zero; division by zero is a runtime error."),
    "MOD": ("-", "-2 +1", "Pop b, a; push a % b (sign of the dividend); modulo by zero is a runtime error."),
    "SHL": ("-", "-2 +1", "Pop k, a; push a << k (32-bit wrapping)."),
    "SHR": ("-", "-2 +1", "Pop k, a; push a >> k (arithmetic shift)."),
    "NEG": ("-", "0", "Negate the top of the stack."),
    "NOT": ("-", "0", "Logical negation of the top of the stack."),
    "I2F": ("-", "0", "Convert the top of the stack from int to float."),
    "LT": ("-", "-2 +1", "Pop b, a; push a < b."),
    "LE": ("-", "-2 +1", "Pop b, a; push a <= b."),
    "GT": ("-", "-2 +1", "Pop b, a; push a > b."),
    "GE": ("-", "-2 +1", "Pop b, a; push a >= b."),
    "EQ": ("-", "-2 +1", "Pop b, a; push a == b."),
    "NE": ("-", "-2 +1", "Pop b, a; push a != b."),
    "JUMP": ("target pc", "0", "Unconditional jump."),
    "JUMP_IF_FALSE": ("target pc", "-1", "Pop a bool; jump if it is false."),
    "CALL": ("function/argc", "-argc +ret", "Call a function; arguments are popped, the return value (if any) is pushed."),
    "RETURN": ("-", "-1", "Return the top of the stack to the caller."),
    "RETURN_VOID": ("-", "0", "Return to the caller without a value."),
    "PRINT": ("-", "-1", "Pop a value and append it to the program output."),
    "POP": ("-", "-1", "Discard the top of the stack."),
    "HALT": ("-", "0", "Stop the machine."),
}
BINARY = ("ADD", "SUB", "MUL", "DIV", "MOD", "SHL", "SHR", "LT", "LE", "GT", "GE", "EQ", "NE")


def const_text(v: Any) -> str:
    if type(v) is bool:
        return "true" if v else "false"
    if type(v) is str:
        return json.dumps(v)
    return repr(v)


@dataclass
class BInstr:
    pc: int
    op: str
    arg: Any = None
    arg2: Optional[int] = None
    fn: str = ""
    ir_id: Optional[int] = None
    origins: List[int] = field(default_factory=list)
    arg_text: str = ""

    def text(self) -> str:
        if self.op == "PUSH":
            return f"PUSH {const_text(self.arg)}"
        if self.op in ("LOAD", "STORE"):
            return f"{self.op} {self.arg_text}"
        if self.op in ("GLOAD", "GSTORE"):
            return f"{self.op} @{self.arg}"
        if self.op in ("JUMP", "JUMP_IF_FALSE"):
            return f"{self.op} @{self.arg}"
        if self.op == "CALL":
            return f"CALL {self.arg}/{self.arg2}"
        return self.op

    def to_dict(self) -> dict:
        return {"pc": self.pc, "op": self.op, "text": self.text(), "function": self.fn,
                "irId": self.ir_id, "origins": self.origins,
                "arg": self.arg if type(self.arg) in (int, str, bool, float, type(None)) else str(self.arg)}


@dataclass
class BFunction:
    name: str
    entry: int
    end: int
    nparams: int
    nlocals: int
    locals: List[str]
    return_type: str


@dataclass
class BProgram:
    code: List[BInstr]
    functions: Dict[str, BFunction]
    globals: List[Dict[str, str]]
    label: str = ""

    def to_dict(self) -> dict:
        return {
            "label": self.label, "size": len(self.code),
            "instructions": [i.to_dict() for i in self.code],
            "functions": [{"name": f.name, "entry": f.entry, "end": f.end, "params": f.nparams,
                           "locals": f.nlocals, "localNames": f.locals, "returnType": f.return_type}
                          for f in self.functions.values()],
            "globals": self.globals,
        }

    def listing(self) -> str:
        return "\n".join(f"{i.pc:>4}  {i.text():<26} ; {i.fn}" + (f" ir#{i.ir_id}" if i.ir_id else "")
                         for i in self.code)
