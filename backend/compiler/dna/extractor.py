"""Program DNA: a deterministic, explainable structural profile of a program.

Every field is derived from the real AST, semantic result, IR and CFG of the
program being compiled. Nothing is sampled or invented; the same program
always yields the same DNA.
"""

from __future__ import annotations

import hashlib
import math
import time
from collections import Counter
from typing import Dict, List, Optional, Set

from compiler.ast import nodes as N
from compiler.ast.builder import ASTResult
from compiler.cfg.builder import CFGResult
from compiler.evolution.passes import count_opportunities
from compiler.ir.instructions import IRProgram
from compiler.semantic.analyzer import SemanticResult

ARITH_OPS = ("ADD", "SUB", "MUL", "DIV", "MOD", "NEG")
SHIFT_OPS = ("SHL", "SHR")
CMP_OPS = ("LT", "LE", "GT", "GE", "EQ", "NE")
CONTROL_OPS = ("JMP", "CBR", "RET")


def _h(s: str, n: int = 16) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:n]


def _control_nesting(node: N.Node, depth: int = 0) -> int:
    best = depth
    inc = 1 if isinstance(node, (N.IfStatement, N.WhileStatement, N.ForStatement)) else 0
    for _, c in node.children():
        best = max(best, _control_nesting(c, depth + inc))
    return best if not inc else max(best, depth + 1)


def _cycles(graph: Dict[str, Set[str]]) -> List[str]:
    """Functions that can (transitively) reach themselves."""
    rec = []
    for f in graph:
        seen: Set[str] = set()
        stack = list(graph[f])
        while stack:
            x = stack.pop()
            if x == f:
                rec.append(f)
                break
            if x in seen or x not in graph:
                continue
            seen.add(x)
            stack.extend(graph[x])
    return sorted(rec)


def extract_dna(source: str, ast: ASTResult, sem: SemanticResult, ir: IRProgram, cfg: CFGResult,
                opportunities: Optional[Dict[str, int]] = None) -> dict:
    t0 = time.perf_counter()
    nodes = [ast.nodes[i] for i in ast.order]

    # ---- signatures -----------------------------------------------------
    structural = "|".join(f"{ast.depth[n.id]}:{n.node_type}" for n in nodes)
    fingerprint = "|".join(f"{ast.depth[n.id]}:{n.node_type}:{sorted((k, str(v)) for k, v in n.attributes().items())}"
                           for n in nodes)
    cf_parts = []
    for f in cfg.functions:
        pos = {b: i for i, b in enumerate(f.rpo)}
        rows = []
        for b in f.rpo:
            blk = f.blocks[b]
            rows.append(f"{blk.terminator}>" + ",".join(f"{pos.get(t, '?')}{k[0]}" for t, k in blk.succ))
        cf_parts.append(f"{'fn'}[{';'.join(rows)}]")
    cf_string = " ".join(cf_parts)
    ir_string = " ".join(f"{i.op}:{i.ty or ''}" for _, i in ir.all_instrs())

    # ---- operator / literal profile (AST) -------------------------------
    ops: Counter = Counter()
    unary: Counter = Counter()
    literals: Counter = Counter()
    ints: List[int] = []
    strings_len = 0
    for n in nodes:
        if isinstance(n, N.BinaryExpression):
            ops[n.operator] += 1
        elif isinstance(n, N.UnaryExpression):
            unary[n.operator] += 1
        elif isinstance(n, N.Assignment) and n.operator != "=":
            ops[n.operator] += 1
        elif isinstance(n, N.IncDecStatement):
            ops[n.operator] += 1
        elif isinstance(n, N.Literal):
            literals[n.lit_type] += 1
            if n.lit_type == "int":
                ints.append(n.value)
            if n.lit_type == "string":
                strings_len += len(n.value)
    arithmetic_ast = sum(v for k, v in ops.items() if k in ("+", "-", "*", "/", "%", "+=", "-=", "*=", "/=", "++", "--"))
    comparison_ast = sum(v for k, v in ops.items() if k in ("<", "<=", ">", ">=", "==", "!="))
    logical_ast = sum(v for k, v in ops.items() if k in ("&&", "||")) + unary.get("!", 0)

    # ---- structure ------------------------------------------------------
    fors = sum(1 for n in nodes if isinstance(n, N.ForStatement))
    whiles = sum(1 for n in nodes if isinstance(n, N.WhileStatement))
    ifs = [n for n in nodes if isinstance(n, N.IfStatement)]
    calls = [n for n in nodes if isinstance(n, N.FunctionCall)]
    fns = [n for n in nodes if isinstance(n, N.FunctionDeclaration)]
    graph: Dict[str, Set[str]] = {f.name: set() for f in fns}
    for f in fns:
        for x in N.walk(f):
            if isinstance(x, N.FunctionCall):
                graph[f.name].add(x.name)
    recursive = _cycles(graph)
    nesting = _control_nesting(ast.root)

    # ---- instruction profile ---------------------------------------------
    opcodes: Counter = Counter()
    total_instr = 0
    for _, i in ir.all_instrs():
        opcodes[i.op] += 1
        if i.op != "LABEL":
            total_instr += 1
    cat = {
        "arithmetic": sum(opcodes[o] for o in ARITH_OPS),
        "shift": sum(opcodes[o] for o in SHIFT_OPS),
        "comparison": sum(opcodes[o] for o in CMP_OPS),
        "logical": opcodes["NOT"],
        "dataMovement": opcodes["MOV"],
        "conversion": opcodes["I2F"],
        "controlFlow": sum(opcodes[o] for o in CONTROL_OPS),
        "calls": opcodes["CALL"],
        "io": opcodes["PRINT"],
    }

    # ---- data flow -------------------------------------------------------
    defs = uses = const_ops = all_ops = copies = 0
    temps: Set[tuple] = set()
    vars_: Set[tuple] = set()
    for f, i in ir.all_instrs():
        if i.dest is not None:
            defs += 1
            (temps if i.dest.kind == "temp" else vars_).add((f.name, i.dest.name)) if i.dest.is_local() else None
        for o in i.operands_read():
            all_ops += 1
            if o.is_const():
                const_ops += 1
            elif o.is_local():
                uses += 1
        if i.op == "MOV" and i.dest is not None and i.dest.is_local() and i.a is not None and i.a.is_local():
            copies += 1
    for f in ir.functions:
        for p in f.params:
            vars_.add((f.name, p.name))

    # ---- loops from the CFG ------------------------------------------------
    loop_rows = []
    loop_instr = 0
    for f in cfg.functions:
        for l in f.loops:
            n_ins = sum(len([x for x in f.blocks[b].instrs if x.op != "LABEL"]) for b in l.body)
            loop_instr += n_ins
            loop_rows.append({"function": f.name, "header": f"B{l.header}", "blocks": len(l.body),
                              "instructions": n_ins, "depth": l.depth})
    cfg_stats = cfg.to_dict()["statistics"]

    # ---- Halstead --------------------------------------------------------------
    operators_all = list(ops.elements()) + list(unary.elements()) + ["=" for n in nodes if isinstance(n, N.Assignment)] \
        + ["call" for _ in calls]
    operands_all = [n.name for n in nodes if isinstance(n, N.Identifier)] + [n.raw for n in nodes if isinstance(n, N.Literal)]
    n1, n2 = len(set(operators_all)), len(set(operands_all))
    N1, N2 = len(operators_all), len(operands_all)
    volume = round((N1 + N2) * math.log2(n1 + n2), 3) if n1 + n2 > 1 else 0.0

    opps = opportunities if opportunities is not None else count_opportunities(ir)
    max_depth = max(ast.depth.values()) if ast.depth else 0

    features = {
        "astNodes": len(nodes), "astDepth": max_depth, "functions": len(fns), "calls": len(calls),
        "blocks": cfg_stats["blocks"], "edges": cfg_stats["edges"], "branches": cfg_stats["branches"],
        "loops": cfg_stats["loops"], "maxLoopDepth": cfg_stats["maxLoopDepth"],
        "cyclomatic": cfg_stats["cyclomaticComplexity"], "irInstructions": total_instr,
        "arithmeticInstr": cat["arithmetic"], "comparisonInstr": cat["comparison"],
        "dataMovementInstr": cat["dataMovement"], "controlInstr": cat["controlFlow"],
        "constantOperandRatio": round(const_ops / all_ops, 4) if all_ops else 0.0,
        "opportunitySites": sum(v for k, v in opps.items() if not k.startswith("spec_")),
    }
    bars = [
        {"key": "ast", "label": "AST structure", "value": len(nodes), "unit": "nodes"},
        {"key": "cfg", "label": "Control flow", "value": cfg_stats["blocks"], "unit": "blocks"},
        {"key": "loops", "label": "Loops", "value": cfg_stats["loops"], "unit": "loops"},
        {"key": "branches", "label": "Branches", "value": cfg_stats["branches"], "unit": "cond. branches"},
        {"key": "arith", "label": "Arithmetic", "value": cat["arithmetic"] + cat["shift"], "unit": "instr"},
        {"key": "cmp", "label": "Comparisons", "value": cat["comparison"], "unit": "instr"},
        {"key": "mem", "label": "Memory / data movement", "value": cat["dataMovement"], "unit": "instr"},
        {"key": "calls", "label": "Calls", "value": cat["calls"], "unit": "instr"},
    ]
    return {
        "programId": _h(source, 12),
        "signatures": {
            "structural": _h(structural), "astFingerprint": _h(fingerprint),
            "controlFlow": _h(cf_string), "controlFlowCanonical": cf_string, "ir": _h(ir_string),
        },
        "operatorProfile": {"binary": dict(sorted(ops.items())), "unary": dict(sorted(unary.items())),
                            "arithmetic": arithmetic_ast, "comparison": comparison_ast, "logical": logical_ast},
        "literalProfile": {
            "byType": dict(literals), "total": sum(literals.values()),
            "distinctInts": len(set(ints)), "zeros": sum(1 for v in ints if v == 0),
            "ones": sum(1 for v in ints if v == 1),
            "powersOfTwo": sum(1 for v in ints if v >= 2 and v & (v - 1) == 0),
            "stringCharacters": strings_len,
        },
        "loopProfile": {"forLoops": fors, "whileLoops": whiles, "cfgLoops": cfg_stats["loops"],
                        "maxDepth": cfg_stats["maxLoopDepth"], "loops": loop_rows,
                        "loopInstructionShare": round(loop_instr / total_instr, 4) if total_instr else 0.0},
        "branchProfile": {"ifStatements": len(ifs), "ifElse": sum(1 for i in ifs if i.else_branch is not None),
                          "conditionalBranches": cfg_stats["branches"], "shortCircuitOperators":
                              ops.get("&&", 0) + ops.get("||", 0), "maxControlNesting": nesting},
        "functionProfile": {"count": len(fns), "averageParameters":
                            round(sum(len(f.params) for f in fns) / len(fns), 3) if fns else 0.0,
                            "callSites": len(calls), "callGraph": {k: sorted(v) for k, v in graph.items()},
                            "recursive": recursive, "leafFunctions": sorted(k for k, v in graph.items() if not v)},
        "instructionProfile": {"total": total_instr, "opcodes": dict(sorted(opcodes.items())), "categories": cat,
                               "categoryShare": {k: round(v / total_instr, 4) if total_instr else 0.0
                                                 for k, v in cat.items()}},
        "dataFlow": {"definitions": defs, "uses": uses,
                     "averageUsesPerDefinition": round(uses / defs, 3) if defs else 0.0,
                     "temporaries": len(temps), "variables": len(vars_ - temps),
                     "globals": len(ir.globals), "copyInstructions": copies,
                     "constantOperands": const_ops, "totalOperands": all_ops,
                     "constantOperandRatio": round(const_ops / all_ops, 4) if all_ops else 0.0},
        "complexityFeatures": {
            "cyclomaticComplexity": cfg_stats["cyclomaticComplexity"], "astDepth": max_depth,
            "astNodes": len(nodes), "irInstructions": total_instr, "basicBlocks": cfg_stats["blocks"],
            "maxControlNesting": nesting,
            "halstead": {"distinctOperators": n1, "distinctOperands": n2, "totalOperators": N1,
                         "totalOperands": N2, "volume": volume},
        },
        "optimizationOpportunities": opps,
        "features": features, "bars": bars,
        "extractMs": round((time.perf_counter() - t0) * 1000, 4),
    }
