"""Optimisation passes over the IR.

Every pass mutates ``fn.instrs`` in place (callers deep-copy first) and
returns a list of *real* transformation records: what changed, the before and
after instruction text, and why.

Sound passes preserve observable behaviour by construction. The ``spec_*``
passes are deliberately *speculative*: they encode common compiler-heuristic
assumptions that are NOT always true (e.g. "calls are pure"). They exist so
the evolutionary search can propose aggressive candidates and the Digital Twin
has genuine work to do rejecting the ones that change behaviour.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from compiler.cfg.builder import build_function_cfg
from compiler.ir.instructions import COMMUTATIVE, Instr, IRFunction, IRProgram, Operand
from compiler.runtime import BINARY_OPS, COMPARE_OPS, EvoRuntimeError, UNARY_OPS, binary_op, unary_op

NAC = "NAC"
PURE_OPS = ("MOV", "ADD", "SUB", "MUL", "NEG", "NOT", "I2F", "SHL", "SHR") + COMPARE_OPS


def _rec(pass_name: str, fn: IRFunction, before: List[Instr], after: List[Instr], reason: str,
         sound: bool = True) -> dict:
    return {
        "pass": pass_name, "function": fn.name, "sound": sound,
        "before": [i.text() for i in before], "after": [i.text() for i in after],
        "beforeOrigins": sorted({o for i in before for o in i.origins}),
        "afterOrigins": sorted({o for i in after for o in i.origins}),
        "reason": reason,
    }


def _mov(ins: Instr, value: Operand) -> Instr:
    return ins.clone(op="MOV", a=value, b=None, ty=ins.dest.type if ins.dest else value.type)  # type: ignore[union-attr]


def _result_type(op: str, ty: Optional[str]) -> str:
    if op in COMPARE_OPS or op == "NOT":
        return "bool"
    if op == "I2F":
        return "float"
    return ty or "int"


def is_pure(ins: Instr) -> bool:
    """True if removing the instruction (when its result is unused) cannot
    change observable behaviour."""
    op = ins.op
    if op == "MOV":
        return ins.dest is not None and ins.dest.is_local()
    if op in ("DIV", "MOD"):
        return ins.b is not None and ins.b.is_const() and ins.b.value != 0
    return op in PURE_OPS


# --------------------------------------------------------------------------- folding
def constant_folding(fn: IRFunction) -> List[dict]:
    recs = []
    for k, ins in enumerate(fn.instrs):
        new = None
        if ins.op in BINARY_OPS and ins.a.is_const() and ins.b.is_const():  # type: ignore[union-attr]
            try:
                v = binary_op(ins.op, ins.a.value, ins.b.value)  # type: ignore[union-attr]
            except EvoRuntimeError:
                continue  # keep the fault for run time
            new = _mov(ins, Operand.const(v, _result_type(ins.op, ins.ty)))
            reason = "Both operands are compile-time constants, so the operation is evaluated now."
        elif ins.op in UNARY_OPS and ins.a.is_const():  # type: ignore[union-attr]
            v = unary_op(ins.op, ins.a.value)  # type: ignore[union-attr]
            new = _mov(ins, Operand.const(v, _result_type(ins.op, ins.ty)))
            reason = "The operand is a compile-time constant, so the operation is evaluated now."
        if new is not None:
            recs.append(_rec("constant_folding", fn, [ins], [new], reason))
            fn.instrs[k] = new
    return recs


# ------------------------------------------------------------ constant propagation
def _meet(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a == b:
        return a
    return NAC


def _resolve(state: Dict[str, object], o: Optional[Operand]) -> Optional[Operand]:
    if o is not None and o.is_local():
        v = state.get(o.name)  # type: ignore[arg-type]
        if isinstance(v, tuple):
            return Operand.const(v[2], v[1])
    return o


def _transfer(state: Dict[str, object], ins: Instr) -> None:
    for d in ins.defs():
        if ins.op == "MOV":
            src = _resolve(state, ins.a)
            state[d] = ("c", src.type, src.value) if src is not None and src.is_const() else NAC
        else:
            state[d] = NAC


def constant_propagation(fn: IRFunction) -> List[dict]:
    cfg = build_function_cfg(fn)
    blocks = cfg.blocks
    out: Dict[int, Dict[str, object]] = {}
    ins_state: Dict[int, Dict[str, object]] = {}
    entry_state = {p.name: NAC for p in fn.params}
    changed = True
    rounds = 0
    while changed and rounds < 200:
        changed = False
        rounds += 1
        for bi in cfg.rpo:
            b = blocks[bi]
            if bi == 0:
                st = dict(entry_state)
            else:
                st = None
                for p in b.pred:
                    if p in out:
                        if st is None:
                            st = dict(out[p])
                        else:
                            for name in set(st) | set(out[p]):
                                m = _meet(st.get(name), out[p].get(name))
                                if m is None:
                                    st.pop(name, None)
                                else:
                                    st[name] = m
                if st is None:
                    continue
            ins_state[bi] = dict(st)
            for ins in b.instrs:
                _transfer(st, ins)
            if out.get(bi) != st:
                out[bi] = st
                changed = True
    recs = []
    for bi in cfg.rpo:
        if bi not in ins_state:
            continue
        b = blocks[bi]
        st = dict(ins_state[bi])
        for off, ins in enumerate(b.instrs):
            k = b.start + off
            na = _resolve(st, ins.a)
            nb = _resolve(st, ins.b)
            nargs = [_resolve(st, a) for a in ins.args]
            if na is not ins.a or nb is not ins.b or any(x is not y for x, y in zip(nargs, ins.args)):
                new = ins.clone(a=na, b=nb, args=nargs)  # type: ignore[arg-type]
                recs.append(_rec("constant_propagation", fn, [ins], [new],
                                 "A variable read here always holds the same compile-time constant on every "
                                 "path reaching this point, so its value is substituted."))
                fn.instrs[k] = new
                _transfer(st, new)
            else:
                _transfer(st, ins)
    return recs


# ------------------------------------------------------------ copy propagation
def copy_propagation(fn: IRFunction) -> List[dict]:
    cfg = build_function_cfg(fn)
    recs = []
    for b in cfg.blocks:
        copies: Dict[str, Operand] = {}
        for off, ins in enumerate(b.instrs):
            k = b.start + off

            def sub(o: Optional[Operand]) -> Optional[Operand]:
                if o is not None and o.is_local() and o.name in copies:
                    return copies[o.name]  # type: ignore[index]
                return o

            na, nb = sub(ins.a), sub(ins.b)
            nargs = [sub(a) for a in ins.args]
            cur = ins
            if na is not ins.a or nb is not ins.b or any(x is not y for x, y in zip(nargs, ins.args)):
                cur = ins.clone(a=na, b=nb, args=nargs)  # type: ignore[arg-type]
                recs.append(_rec("copy_propagation", fn, [ins], [cur],
                                 "This operand is a plain copy of another variable that is unchanged since the "
                                 "copy, so the original is used directly."))
                fn.instrs[k] = cur
            for d in cur.defs():
                copies.pop(d, None)
                for key in [key for key, v in copies.items() if v.name == d]:
                    del copies[key]
            if cur.op == "MOV" and cur.dest is not None and cur.dest.is_local() and cur.a is not None \
                    and cur.a.is_local() and cur.a.name != cur.dest.name:
                copies[cur.dest.name] = cur.a  # type: ignore[index]
    return recs


# ------------------------------------------------------- algebraic simplification
def _c(o: Optional[Operand], value) -> bool:
    return o is not None and o.is_const() and o.type in ("int", "float") and o.value == value \
        and type(o.value) is type(value)


def algebraic_simplification(fn: IRFunction) -> List[dict]:
    recs = []
    for k, ins in enumerate(fn.instrs):
        op, a, b, ty = ins.op, ins.a, ins.b, ins.ty
        new = None
        why = ""
        zero, one = (0, 1) if ty == "int" else (0.0, 1.0)
        if op == "ADD" and ty == "int":
            if _c(b, 0):
                new, why = _mov(ins, a), "x + 0 = x"  # type: ignore[arg-type]
            elif _c(a, 0):
                new, why = _mov(ins, b), "0 + x = x"  # type: ignore[arg-type]
        elif op == "ADD" and ty == "string":
            if b.is_const() and b.value == "":  # type: ignore[union-attr]
                new, why = _mov(ins, a), 'x + "" = x'  # type: ignore[arg-type]
            elif a.is_const() and a.value == "":  # type: ignore[union-attr]
                new, why = _mov(ins, b), '"" + x = x'  # type: ignore[arg-type]
        elif op == "SUB" and ty == "int":
            if _c(b, 0):
                new, why = _mov(ins, a), "x - 0 = x"  # type: ignore[arg-type]
            elif a.is_local() and b.is_local() and a.key() == b.key():  # type: ignore[union-attr]
                new, why = _mov(ins, Operand.const(0, "int")), "x - x = 0"
        elif op == "MUL":
            if ty in ("int", "float") and _c(b, one):
                new, why = _mov(ins, a), "x * 1 = x"  # type: ignore[arg-type]
            elif ty in ("int", "float") and _c(a, one):
                new, why = _mov(ins, b), "1 * x = x"  # type: ignore[arg-type]
            elif ty == "int" and (_c(a, 0) or _c(b, 0)):
                new, why = _mov(ins, Operand.const(0, "int")), "x * 0 = 0"
        elif op == "DIV" and ty in ("int", "float") and _c(b, one):
            new, why = _mov(ins, a), "x / 1 = x"  # type: ignore[arg-type]
        elif op == "MOD" and ty == "int" and (_c(b, 1) or _c(b, -1)):
            new, why = _mov(ins, Operand.const(0, "int")), "x % 1 = 0"
        elif op in COMPARE_OPS and ty in ("int", "string", "bool") and a.is_local() and b.is_local() \
                and a.key() == b.key():  # type: ignore[union-attr]
            v = op in ("EQ", "LE", "GE")
            new, why = _mov(ins, Operand.const(v, "bool")), "comparing a variable with itself has a fixed result"
        if new is not None:
            recs.append(_rec("algebraic_simplification", fn, [ins], [new], f"Algebraic identity: {why}."))
            fn.instrs[k] = new
    return recs


# ------------------------------------------------------------- strength reduction
def strength_reduction(fn: IRFunction) -> List[dict]:
    recs = []
    for k, ins in enumerate(fn.instrs):
        if ins.op != "MUL" or ins.ty != "int":
            continue
        var, const = (ins.a, ins.b) if ins.b.is_const() else (ins.b, ins.a)  # type: ignore[union-attr]
        if not const.is_const() or var.is_const():  # type: ignore[union-attr]
            continue
        v = const.value  # type: ignore[union-attr]
        new = None
        why = ""
        if v == -1:
            new, why = ins.clone(op="NEG", a=var, b=None), "x * -1 becomes a negation (cost 1 instead of 3)."
        elif v >= 2 and (v & (v - 1)) == 0 and v.bit_length() - 1 <= 30:
            sh = v.bit_length() - 1
            new = ins.clone(op="SHL", a=var, b=Operand.const(sh, "int"))
            why = f"Multiplying by {v} (a power of two) is a left shift by {sh} (cost 1 instead of 3); " \
                  f"identical under 32-bit wrapping arithmetic."
        if new is not None:
            recs.append(_rec("strength_reduction", fn, [ins], [new], why))
            fn.instrs[k] = new
    return recs


# ---------------------------------------------- redundant computation elimination
def redundant_computation_elimination(fn: IRFunction) -> List[dict]:
    cfg = build_function_cfg(fn)
    recs = []
    for b in cfg.blocks:
        table: Dict[tuple, Operand] = {}
        for off, ins in enumerate(b.instrs):
            k = b.start + off
            eligible = ins.op in BINARY_OPS + UNARY_OPS and ins.dest is not None and ins.dest.is_local()
            key = None
            if eligible:
                ka = ins.a.key() if ins.a is not None else None  # type: ignore[union-attr]
                kb = ins.b.key() if ins.b is not None else None
                if ins.op in COMMUTATIVE and not (ins.op == "ADD" and ins.ty == "string"):
                    ka, kb = sorted([ka, kb], key=repr)  # type: ignore[type-var]
                key = (ins.op, ins.ty, ka, kb)
            cur = ins
            replaced = False
            if key is not None and key in table:
                holder = table[key]
                cur = _mov(ins, holder)
                recs.append(_rec("redundant_computation_elimination", fn, [ins], [cur],
                                 f"The same computation was already performed in this block and its result is "
                                 f"still held in '{holder.text()}', so it is reused."))
                fn.instrs[k] = cur
                replaced = True
            for d in cur.defs():
                for tk in [tk for tk, h in table.items()
                           if h.name == d or any(isinstance(x, tuple) and len(x) == 2 and x[1] == d
                                                 and x[0] in ("temp", "var") for x in tk[2:])]:
                    del table[tk]
            if key is not None and not replaced and ins.dest.name not in ins.uses():  # type: ignore[union-attr]
                table[key] = ins.dest  # type: ignore[assignment]
    return recs


# --------------------------------------------------------------- dead code
def _live_out(fn: IRFunction):
    cfg = build_function_cfg(fn)
    blocks = cfg.blocks
    use: Dict[int, Set[str]] = {}
    dfn: Dict[int, Set[str]] = {}
    for b in blocks:
        u: Set[str] = set()
        d: Set[str] = set()
        for ins in b.instrs:
            for x in ins.uses():
                if x not in d:
                    u.add(x)
            d.update(ins.defs())
        use[b.index], dfn[b.index] = u, d
    live_in = {b.index: set() for b in blocks}
    live_out = {b.index: set() for b in blocks}
    changed = True
    while changed:
        changed = False
        for b in reversed(cfg.rpo):
            lo: Set[str] = set()
            for t, _ in blocks[b].succ:
                lo |= live_in[t]
            li = use[b] | (lo - dfn[b])
            if lo != live_out[b] or li != live_in[b]:
                live_out[b], live_in[b] = lo, li
                changed = True
    return cfg, live_out


def dead_code_elimination(fn: IRFunction) -> List[dict]:
    recs = []
    while True:
        cfg, live_out = _live_out(fn)
        drop: Set[int] = set()
        for b in cfg.blocks:
            if not b.reachable:
                continue
            live = set(live_out[b.index])
            for off in range(len(b.instrs) - 1, -1, -1):
                ins = b.instrs[off]
                dests = ins.defs()
                if dests and is_pure(ins) and dests[0] not in live:
                    drop.add(b.start + off)
                    recs.append(_rec("dead_code_elimination", fn, [ins], [],
                                     f"'{dests[0]}' is never read after this assignment on any path, "
                                     f"and the computation has no side effects."))
                    continue
                live -= set(dests)
                live |= set(ins.uses())
        if not drop:
            break
        fn.instrs = [i for k, i in enumerate(fn.instrs) if k not in drop]
    return recs



# ------------------------------------------------------------- temp forwarding
def temp_forwarding(fn: IRFunction) -> List[dict]:
    """``t = e ; x = t`` with ``t`` dead afterwards  ->  ``x = e``."""
    recs = []
    cfg, live_out = _live_out(fn)
    drop: Set[int] = set()
    for b in cfg.blocks:
        live = set(live_out[b.index])
        after: List[Set[str]] = [set()] * len(b.instrs)
        for off in range(len(b.instrs) - 1, -1, -1):
            after[off] = set(live)
            ins = b.instrs[off]
            live -= set(ins.defs())
            live |= set(ins.uses())
        for off in range(len(b.instrs) - 1):
            k = b.start + off
            if k in drop or (k + 1) in drop:
                continue
            i1, i2 = fn.instrs[k], fn.instrs[k + 1]
            if i1.dest is None or not i1.dest.is_local() or i1.op in ("LABEL", "JMP", "CBR", "RET", "PRINT"):
                continue
            if i2.op != "MOV" or i2.a is None or i2.a.key() != i1.dest.key():
                continue
            if i2.dest is None or not i2.dest.is_local() or i2.dest.key() == i1.dest.key():
                continue
            if i1.dest.name in after[off + 1]:
                continue
            new = i1.clone(dest=i2.dest, origins=sorted(set(i1.origins) | set(i2.origins)))
            recs.append(_rec("temp_forwarding", fn, [i1, i2], [new],
                             f"'{i1.dest.name}' only carries this result into '{i2.dest.name}' and is dead "
                             f"afterwards, so the result is computed directly into '{i2.dest.name}'."))
            fn.instrs[k] = new
            drop.add(k + 1)
    if drop:
        fn.instrs = [i for k, i in enumerate(fn.instrs) if k not in drop]
    return recs


# --------------------------------------------------------- branch simplification
def branch_simplification(fn: IRFunction) -> List[dict]:
    recs = []
    progress = True
    while progress:
        progress = False
        for k, ins in enumerate(fn.instrs):
            if ins.op == "CBR":
                target = None
                if ins.a.is_const():  # type: ignore[union-attr]
                    target = ins.label if ins.a.value else ins.label2  # type: ignore[union-attr]
                    why = f"The branch condition is the constant {ins.a.text()}, so only one target is reachable."  # type: ignore[union-attr]
                elif ins.label == ins.label2:
                    target, why = ins.label, "Both branch targets are identical."
                if target is not None:
                    new = ins.clone(op="JMP", a=None, label=target, label2=None)
                    recs.append(_rec("branch_simplification", fn, [ins], [new], why))
                    fn.instrs[k] = new
                    progress = True
        cfg = build_function_cfg(fn)
        dead = [b for b in cfg.blocks if not b.reachable]
        if dead:
            drop = {b.start + o for b in dead for o in range(len(b.instrs))}
            for b in dead:
                real = [i for i in b.instrs if i.op != "LABEL"]
                if real:
                    recs.append(_rec("branch_simplification", fn, real, [],
                                     "This block can never be reached from the function entry."))
            fn.instrs = [i for k, i in enumerate(fn.instrs) if k not in drop]
            progress = True
        # jump to the immediately following label
        out: List[Instr] = []
        n = len(fn.instrs)
        for k, ins in enumerate(fn.instrs):
            if ins.op == "JMP":
                j = k + 1
                following = set()
                while j < n and fn.instrs[j].op == "LABEL":
                    following.add(fn.instrs[j].label)
                    j += 1
                if ins.label in following:
                    recs.append(_rec("branch_simplification", fn, [ins], [],
                                     "The jump targets the very next instruction, so it is redundant."))
                    progress = True
                    continue
            out.append(ins)
        fn.instrs = out
        used = {l for i in fn.instrs for l in i.labels_referenced()}
        kept = [i for i in fn.instrs if not (i.op == "LABEL" and i.label not in used)]
        if len(kept) != len(fn.instrs):
            fn.instrs = kept
            progress = True
    return recs


# ---------------------------------------------------------- speculative passes
def spec_div_to_shift(fn: IRFunction) -> List[dict]:
    """Speculative: assume x / 2^k == x >> k. Wrong for negative dividends
    (division truncates toward zero, an arithmetic shift rounds down)."""
    recs = []
    for k, ins in enumerate(fn.instrs):
        if ins.op == "DIV" and ins.ty == "int" and ins.b.is_const() and ins.b.value >= 2 \
                and (ins.b.value & (ins.b.value - 1)) == 0:  # type: ignore[union-attr]
            sh = ins.b.value.bit_length() - 1  # type: ignore[union-attr]
            new = ins.clone(op="SHR", b=Operand.const(sh, "int"))
            recs.append(_rec("spec_div_to_shift", fn, [ins], [new],
                             f"Speculation: dividing by {ins.b.value} is assumed equal to shifting right by {sh}. "  # type: ignore[union-attr]
                             f"This is only true for non-negative dividends.", sound=False))
            fn.instrs[k] = new
    return recs


def spec_drop_unused_calls(fn: IRFunction) -> List[dict]:
    """Speculative: assume a call whose result is unused has no side effects.
    Wrong whenever the callee prints or writes a global."""
    recs = []
    used = {u for i in fn.instrs for u in i.uses()}
    keep = []
    for ins in fn.instrs:
        if ins.op == "CALL" and (ins.dest is None or ins.dest.name not in used):
            recs.append(_rec("spec_drop_unused_calls", fn, [ins], [],
                             f"Speculation: the result of '{ins.func}' is unused, so the call is assumed to be "
                             f"side-effect free and removed.", sound=False))
            continue
        keep.append(ins)
    fn.instrs = keep
    return recs


@dataclass
class PassInfo:
    name: str
    label: str
    sound: bool
    description: str
    run: Callable[[IRFunction], List[dict]]


PASSES: Dict[str, PassInfo] = {p.name: p for p in [
    PassInfo("constant_folding", "Constant folding", True,
             "Evaluate operations whose operands are all compile-time constants.", constant_folding),
    PassInfo("constant_propagation", "Constant propagation", True,
             "Replace variable reads by constants using forward dataflow over the CFG.", constant_propagation),
    PassInfo("copy_propagation", "Copy propagation", True,
             "Replace reads of a copied variable by the original within a basic block.", copy_propagation),
    PassInfo("algebraic_simplification", "Algebraic simplification", True,
             "Apply safe identities (x+0, x*1, x-x, ...).", algebraic_simplification),
    PassInfo("strength_reduction", "Strength reduction", True,
             "Replace expensive multiplications by shifts/negations.", strength_reduction),
    PassInfo("redundant_computation_elimination", "Redundant computation elimination", True,
             "Reuse the result of an identical earlier computation in the same block.",
             redundant_computation_elimination),
    PassInfo("temp_forwarding", "Temp forwarding (copy coalescing)", True,
             "Compute a result directly into its destination instead of via a dead temporary.", temp_forwarding),
    PassInfo("dead_code_elimination", "Dead-code elimination", True,
             "Remove side-effect-free instructions whose result is never read (liveness dataflow).",
             dead_code_elimination),
    PassInfo("branch_simplification", "Branch simplification", True,
             "Fold constant branches, drop unreachable blocks, redundant jumps and unused labels.",
             branch_simplification),
    PassInfo("spec_div_to_shift", "Speculative: divide-by-2^k as shift", False,
             "Unsound heuristic: x / 2^k -> x >> k (wrong for negative x).", spec_div_to_shift),
    PassInfo("spec_drop_unused_calls", "Speculative: drop unused calls", False,
             "Unsound heuristic: assume calls with unused results are pure.", spec_drop_unused_calls),
]}

SOUND_PASSES = [n for n, p in PASSES.items() if p.sound]
SPECULATIVE_PASSES = [n for n, p in PASSES.items() if not p.sound]
STANDARD_PIPELINE = [
    "constant_propagation", "constant_folding", "branch_simplification", "copy_propagation",
    "algebraic_simplification", "strength_reduction", "redundant_computation_elimination",
    "temp_forwarding", "dead_code_elimination",
] * 2


def apply_pass(program: IRProgram, name: str) -> List[dict]:
    recs: List[dict] = []
    for fn in program.functions:
        recs.extend(PASSES[name].run(fn))
    return recs


def apply_genome(original: IRProgram, genome: List[str]) -> Tuple[IRProgram, List[dict]]:
    """Apply passes in order to a deep copy of ``original``. Returns the new
    IR (renumbered) and one history entry per pass application."""
    prog = copy.deepcopy(original)
    history = []
    for step, name in enumerate(genome):
        recs = apply_pass(prog, name)
        history.append({"step": step + 1, "pass": name, "sound": PASSES[name].sound,
                        "changed": bool(recs), "changes": len(recs), "records": recs})
    prog.renumber()
    return prog, history


def count_opportunities(program: IRProgram) -> Dict[str, int]:
    """Dry-run each pass on a copy and count how many sites it would change.
    Used by Program DNA to describe (and guide) optimisation potential."""
    out: Dict[str, int] = {}
    for name in PASSES:
        prog = copy.deepcopy(program)
        out[name] = len(apply_pass(prog, name))
    return out
