"""Reference interpreter for the IR.

This is the engine the Digital Twin uses to execute the *original* program and
every optimisation candidate. It also measures a deterministic dynamic cost
(sum of per-opcode weights of executed instructions) used by the fitness
function.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from compiler.runtime import (EvoRuntimeError, binary_op, default_value, format_value, unary_op)
from .instructions import COST_WEIGHTS, Instr, IRFunction, IRProgram, Operand

MAX_CALL_DEPTH = 200


@dataclass
class RunResult:
    status: str                    # OK | RUNTIME_ERROR | STEP_LIMIT
    output: List[str] = field(default_factory=list)
    return_value: Any = None
    return_type: Optional[str] = None
    error_kind: Optional[str] = None
    error_message: Optional[str] = None
    executed: int = 0
    cost: int = 0
    globals_state: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def behavior(self) -> dict:
        """The observable behaviour compared by the Digital Twin."""
        return {
            "status": self.status,
            "output": list(self.output),
            "returnValue": _jsonable(self.return_value),
            "error": self.error_kind,
            "globals": {k: _jsonable(v) for k, v in sorted(self.globals_state.items())},
        }

    def summary(self) -> dict:
        return {
            "status": self.status, "output": "\n".join(self.output),
            "outputLines": list(self.output),
            "returnValue": None if self.return_value is None else format_value(self.return_value),
            "error": (f"{self.error_kind}: {self.error_message}" if self.error_kind else None),
            "executed": self.executed, "cost": self.cost,
        }


def _jsonable(v: Any):
    if type(v) is float and (v != v or v in (float("inf"), float("-inf"))):
        return repr(v)
    return v


class _StepLimit(Exception):
    pass


class Interpreter:
    def __init__(self, program: IRProgram, step_limit: int = 200_000):
        self.program = program
        self.funcs: Dict[str, IRFunction] = {f.name: f for f in program.functions}
        self.labels: Dict[str, Dict[str, int]] = {}
        for f in program.functions:
            self.labels[f.name] = {i.label: k for k, i in enumerate(f.instrs) if i.op == "LABEL"}  # type: ignore[misc]
        self.step_limit = step_limit
        self.output: List[str] = []
        self.globals: Dict[str, Any] = {g["name"]: default_value(g["type"]) for g in program.globals}
        self.executed = 0
        self.cost = 0
        self.depth = 0

    def run(self, entry: Optional[str] = None, args: Optional[List[Any]] = None) -> RunResult:
        entry = entry or self.program.entry
        t0 = time.perf_counter()
        status, ret, kind, msg = "OK", None, None, None
        try:
            ret = self.call(entry, args or [])
        except EvoRuntimeError as e:
            status, kind, msg = "RUNTIME_ERROR", e.kind, e.message
        except _StepLimit:
            status, kind, msg = "STEP_LIMIT", "StepLimit", f"exceeded {self.step_limit} executed instructions"
        return RunResult(status, self.output, ret, self.funcs[entry].return_type, kind, msg,
                         self.executed, self.cost, dict(self.globals),
                         (time.perf_counter() - t0) * 1000)

    def call(self, name: str, args: List[Any]) -> Any:
        f = self.funcs[name]
        self.depth += 1
        if self.depth > MAX_CALL_DEPTH:
            raise EvoRuntimeError("StackOverflow", f"call depth exceeded {MAX_CALL_DEPTH}")
        env: Dict[str, Any] = {p.name: a for p, a in zip(f.params, args)}
        instrs, labels = f.instrs, self.labels[name]
        n = len(instrs)
        pc = 0
        limit = self.step_limit
        while pc < n:
            ins = instrs[pc]
            op = ins.op
            pc += 1
            if op == "LABEL":
                continue
            self.executed += 1
            self.cost += COST_WEIGHTS[op]
            if self.executed > limit:
                raise _StepLimit()
            if op == "MOV":
                self._set(env, ins.dest, self._get(env, ins.a))
            elif op in ("NEG", "NOT", "I2F"):
                self._set(env, ins.dest, unary_op(op, self._get(env, ins.a)))
            elif op == "JMP":
                pc = labels[ins.label]  # type: ignore[index]
            elif op == "CBR":
                pc = labels[ins.label if self._get(env, ins.a) else ins.label2]  # type: ignore[index]
            elif op == "RET":
                self.depth -= 1
                return self._get(env, ins.a) if ins.a is not None else None
            elif op == "PRINT":
                self.output.append(format_value(self._get(env, ins.a)))
            elif op == "CALL":
                r = self.call(ins.func, [self._get(env, a) for a in ins.args])  # type: ignore[arg-type]
                if ins.dest is not None:
                    self._set(env, ins.dest, r)
            else:
                self._set(env, ins.dest, binary_op(op, self._get(env, ins.a), self._get(env, ins.b)))
        self.depth -= 1
        return None

    def _get(self, env: Dict[str, Any], o: Optional[Operand]) -> Any:
        if o.kind == "const":  # type: ignore[union-attr]
            return o.value  # type: ignore[union-attr]
        if o.kind == "global":  # type: ignore[union-attr]
            return self.globals[o.name]  # type: ignore[union-attr]
        try:
            return env[o.name]  # type: ignore[union-attr,index]
        except KeyError:
            raise EvoRuntimeError("UninitializedVariable", f"'{o.name}' read before assignment")  # type: ignore[union-attr]

    def _set(self, env: Dict[str, Any], o: Operand, v: Any) -> None:
        if o.kind == "global":
            self.globals[o.name] = v  # type: ignore[index]
        else:
            env[o.name] = v  # type: ignore[index]


def run_program(program: IRProgram, step_limit: int = 200_000) -> RunResult:
    return Interpreter(program, step_limit).run()


def run_function(program: IRProgram, name: str, args: List[Any], step_limit: int = 20_000) -> RunResult:
    return Interpreter(program, step_limit).run(name, args)
