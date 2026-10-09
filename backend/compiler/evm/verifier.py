"""Static bytecode verifier: jump targets, slot bounds, call arity and stack depth."""

from __future__ import annotations

from typing import Dict, List

from compiler.codegen.bytecode import BINARY, BProgram


def verify(p: BProgram) -> dict:
    errors: List[str] = []
    per_fn = []
    ret_void = {f.name: f.return_type == "void" for f in p.functions.values()}
    regions = [("<boot>", 0, 2, 0)] + [(f.name, f.entry, f.end, f.nlocals) for f in p.functions.values()]
    for name, lo, hi, nlocals in regions:
        depth_at: Dict[int, int] = {}
        work = [(lo, 0)]
        max_depth = 0
        reached = set()
        while work:
            pc, d = work.pop()
            while True:
                if not (lo <= pc < hi):
                    errors.append(f"{name}: control flow leaves the function at pc {pc}")
                    break
                if pc in depth_at:
                    if depth_at[pc] != d:
                        errors.append(f"{name}: inconsistent stack depth at pc {pc} ({depth_at[pc]} vs {d})")
                    break
                depth_at[pc] = d
                reached.add(pc)
                ins = p.code[pc]
                op = ins.op
                pops = pushes = 0
                if op in ("PUSH", "LOAD", "GLOAD"):
                    pushes = 1
                    if op == "LOAD" and not (0 <= ins.arg < nlocals):
                        errors.append(f"{name}: pc {pc} LOAD slot {ins.arg} out of range")
                elif op in ("STORE", "GSTORE", "PRINT", "POP", "JUMP_IF_FALSE", "RETURN"):
                    pops = 1
                    if op == "STORE" and not (0 <= ins.arg < nlocals):
                        errors.append(f"{name}: pc {pc} STORE slot {ins.arg} out of range")
                elif op in BINARY:
                    pops, pushes = 2, 1
                elif op in ("NEG", "NOT", "I2F"):
                    pops, pushes = 1, 1
                elif op == "CALL":
                    callee = p.functions.get(ins.arg)
                    if callee is None:
                        errors.append(f"{name}: pc {pc} calls unknown function '{ins.arg}'")
                        break
                    if callee.nparams != ins.arg2:
                        errors.append(f"{name}: pc {pc} passes {ins.arg2} args to '{callee.name}' "
                                      f"which takes {callee.nparams}")
                    pops, pushes = ins.arg2 or 0, 0 if ret_void[callee.name] else 1
                if d < pops:
                    errors.append(f"{name}: stack underflow at pc {pc} ({op})")
                    break
                d = d - pops + pushes
                max_depth = max(max_depth, d)
                if op == "RETURN":
                    if d != 0:
                        errors.append(f"{name}: RETURN at pc {pc} leaves {d} extra value(s) on the stack")
                    break
                if op == "RETURN_VOID":
                    if d != 0:
                        errors.append(f"{name}: RETURN_VOID at pc {pc} with non-empty stack")
                    break
                if op == "HALT":
                    break
                if op == "JUMP":
                    pc = ins.arg
                    continue
                if op == "JUMP_IF_FALSE":
                    work.append((ins.arg, d))
                pc += 1
        unreachable = [i for i in range(lo, hi) if i not in reached]
        per_fn.append({"name": name, "instructions": hi - lo, "maxStackDepth": max_depth,
                       "unreachableInstructions": len(unreachable)})
    return {"ok": not errors, "errors": errors, "functions": per_fn,
            "checks": ["jump targets stay inside the function", "local slots in range",
                       "call targets exist and arities match", "no stack underflow",
                       "stack depth is consistent at every join", "RETURN sees exactly the return value"]}
