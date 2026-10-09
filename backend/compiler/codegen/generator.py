"""IR -> EvoVM bytecode. Consumes the (optimised) IR, never source text."""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from compiler.ir.instructions import Instr, IRFunction, IRProgram, Operand
from compiler.runtime import BINARY_OPS
from .bytecode import BFunction, BInstr, BProgram


class _Emit:
    def __init__(self):
        self.items: List[Tuple[BInstr, Optional[str]]] = []  # (instr, symbolic jump label)
        self.labels: Dict[str, int] = {}


def _slots(fn: IRFunction) -> Dict[str, int]:
    slots: Dict[str, int] = {}
    for p in fn.params:
        slots[p.name] = len(slots)  # type: ignore[index]
    for i in fn.instrs:
        for o in ([i.dest] if i.dest is not None else []) + i.operands_read():
            if o.is_local() and o.name not in slots:
                slots[o.name] = len(slots)  # type: ignore[index]
    return slots


def generate_bytecode(ir: IRProgram, label: str = "") -> Tuple[BProgram, float]:
    t0 = time.perf_counter()
    ret_types = {f.name: f.return_type for f in ir.functions}
    code: List[BInstr] = []
    funcs: Dict[str, BFunction] = {}
    # bootstrap stub: call the synthetic entry then halt
    code.append(BInstr(0, "CALL", ir.entry, 0, "<boot>"))
    code.append(BInstr(1, "HALT", fn="<boot>"))
    for f in ir.functions:
        base = len(code)
        slots = _slots(f)
        em = _Emit()

        def emit(op, ins: Instr, arg=None, arg2=None, arg_text="", jump_label=None):
            b = BInstr(0, op, arg, arg2, f.name, ins.id, list(ins.origins), arg_text)
            em.items.append((b, jump_label))

        def push(o: Operand, ins: Instr):
            if o.is_const():
                emit("PUSH", ins, o.value)
            elif o.kind == "global":
                emit("GLOAD", ins, o.name)
            else:
                emit("LOAD", ins, slots[o.name], arg_text=f"{o.name}[{slots[o.name]}]")  # type: ignore[index]

        def store(o: Operand, ins: Instr):
            if o.kind == "global":
                emit("GSTORE", ins, o.name)
            else:
                emit("STORE", ins, slots[o.name], arg_text=f"{o.name}[{slots[o.name]}]")  # type: ignore[index]

        n = len(f.instrs)
        for k, ins in enumerate(f.instrs):
            op = ins.op
            if op == "LABEL":
                em.labels[ins.label] = len(em.items)  # type: ignore[index]
            elif op == "MOV":
                push(ins.a, ins)  # type: ignore[arg-type]
                store(ins.dest, ins)  # type: ignore[arg-type]
            elif op in BINARY_OPS:
                push(ins.a, ins)  # type: ignore[arg-type]
                push(ins.b, ins)  # type: ignore[arg-type]
                emit(op, ins)
                store(ins.dest, ins)  # type: ignore[arg-type]
            elif op in ("NEG", "NOT", "I2F"):
                push(ins.a, ins)  # type: ignore[arg-type]
                emit(op, ins)
                store(ins.dest, ins)  # type: ignore[arg-type]
            elif op == "JMP":
                emit("JUMP", ins, jump_label=ins.label)
            elif op == "CBR":
                push(ins.a, ins)  # type: ignore[arg-type]
                emit("JUMP_IF_FALSE", ins, jump_label=ins.label2)
                j = k + 1
                fallthrough_to_true = False
                while j < n and f.instrs[j].op == "LABEL":
                    if f.instrs[j].label == ins.label:
                        fallthrough_to_true = True
                    j += 1
                if not fallthrough_to_true:
                    emit("JUMP", ins, jump_label=ins.label)
            elif op == "CALL":
                for a in ins.args:
                    push(a, ins)
                emit("CALL", ins, ins.func, len(ins.args))
                if ins.dest is not None:
                    store(ins.dest, ins)
                elif ret_types.get(ins.func) != "void":
                    emit("POP", ins)
            elif op == "RET":
                if ins.a is not None:
                    push(ins.a, ins)
                    emit("RETURN", ins)
                else:
                    emit("RETURN_VOID", ins)
            elif op == "PRINT":
                push(ins.a, ins)  # type: ignore[arg-type]
                emit("PRINT", ins)
            else:
                raise ValueError(f"codegen: unknown IR opcode {op}")
        # resolve labels
        for idx, (b, lbl) in enumerate(em.items):
            b.pc = base + idx
            if lbl is not None:
                b.arg = base + em.labels[lbl]
        code.extend(b for b, _ in em.items)
        funcs[f.name] = BFunction(f.name, base, len(code), len(f.params), len(slots),
                                  list(slots.keys()), f.return_type)
    prog = BProgram(code, funcs, ir.globals, label)
    return prog, (time.perf_counter() - t0) * 1000
