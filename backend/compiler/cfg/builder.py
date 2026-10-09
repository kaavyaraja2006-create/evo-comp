"""Control-flow graph construction from IR.

Algorithm: classic leader identification -> basic blocks -> edges, then
reachability, dominators (iterative dataflow), back edges and natural loops.
Every number reported is computed from the graph built here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from compiler.ir.instructions import Instr, IRFunction, IRProgram


@dataclass
class Block:
    index: int
    start: int                 # index into fn.instrs
    end: int                   # exclusive
    instrs: List[Instr]
    label: Optional[str] = None
    succ: List[Tuple[int, str]] = field(default_factory=list)
    pred: List[int] = field(default_factory=list)
    reachable: bool = True
    exits: bool = False        # ends in RET

    @property
    def id(self) -> str:
        return f"B{self.index}"

    @property
    def terminator(self) -> str:
        last = self.instrs[-1] if self.instrs else None
        if last is None:
            return "empty"
        if last.op in ("JMP", "CBR", "RET"):
            return last.op
        return "FALLTHROUGH"


@dataclass
class Loop:
    header: int
    back_edge_sources: List[int]
    body: List[int]
    depth: int = 1


@dataclass
class FunctionCFG:
    name: str
    blocks: List[Block]
    edges: List[dict]
    loops: List[Loop]
    dominators: Dict[int, Set[int]]
    rpo: List[int]

    def stats(self) -> dict:
        real_edges = len(self.edges)
        n_virtual = 2
        exit_edges = sum(1 for b in self.blocks if b.exits and b.reachable)
        total_nodes = len(self.blocks) + n_virtual
        total_edges = real_edges + 1 + exit_edges
        branches = sum(1 for b in self.blocks if b.terminator == "CBR")
        return {
            "blocks": len(self.blocks), "edges": real_edges, "branches": branches,
            "loops": len(self.loops),
            "maxLoopDepth": max((l.depth for l in self.loops), default=0),
            "unreachableBlocks": sum(1 for b in self.blocks if not b.reachable),
            "cyclomaticComplexity": total_edges - total_nodes + 2,
        }

    def to_dict(self) -> dict:
        headers = {l.header for l in self.loops}
        in_loops: Dict[int, int] = {}
        for l in self.loops:
            for b in l.body:
                in_loops[b] = in_loops.get(b, 0) + 1
        blocks = []
        for b in self.blocks:
            blocks.append({
                "id": b.id, "index": b.index, "label": b.label,
                "instructions": [{"id": i.id, "text": i.text(), "op": i.op, "src": i.src} for i in b.instrs],
                "successors": [{"to": f"B{t}", "kind": k} for t, k in b.succ],
                "predecessors": [f"B{p}" for p in b.pred],
                "terminator": b.terminator,
                "terminatorText": b.instrs[-1].text() if b.instrs else "",
                "reachable": b.reachable, "isLoopHeader": b.index in headers,
                "loopDepth": in_loops.get(b.index, 0), "exits": b.exits,
                "dominators": sorted(f"B{d}" for d in self.dominators.get(b.index, set())),
            })
        virtual = [{"from": "ENTRY", "to": "B0", "kind": "entry"}] if self.blocks else []
        virtual += [{"from": b.id, "to": "EXIT", "kind": "return"} for b in self.blocks if b.exits and b.reachable]
        return {
            "name": self.name, "blocks": blocks, "edges": self.edges, "virtualEdges": virtual,
            "loops": [{"header": f"B{l.header}", "backEdgeSources": [f"B{s}" for s in l.back_edge_sources],
                       "blocks": [f"B{b}" for b in l.body], "depth": l.depth} for l in self.loops],
            "statistics": self.stats(),
        }


def build_function_cfg(fn: IRFunction) -> FunctionCFG:
    instrs = fn.instrs
    n = len(instrs)
    targeted = set()
    for i in instrs:
        targeted.update(i.labels_referenced())
    leaders = {0} if n else set()
    for k, i in enumerate(instrs):
        if i.op == "LABEL" and i.label in targeted:
            leaders.add(k)
        if i.op in ("JMP", "CBR", "RET") and k + 1 < n:
            leaders.add(k + 1)
    order = sorted(leaders)
    blocks: List[Block] = []
    for bi, s in enumerate(order):
        e = order[bi + 1] if bi + 1 < len(order) else n
        blk = Block(bi, s, e, instrs[s:e])
        if blk.instrs and blk.instrs[0].op == "LABEL":
            blk.label = blk.instrs[0].label
        blocks.append(blk)
    label_block: Dict[str, int] = {}
    for b in blocks:
        for i in b.instrs:
            if i.op == "LABEL":
                label_block[i.label] = b.index  # type: ignore[index]
    edges: List[dict] = []

    def add_edge(a: int, b: int, kind: str):
        blocks[a].succ.append((b, kind))
        blocks[b].pred.append(a)

    for b in blocks:
        last = b.instrs[-1] if b.instrs else None
        if last is not None and last.op == "JMP":
            add_edge(b.index, label_block[last.label], "jump")  # type: ignore[index]
        elif last is not None and last.op == "CBR":
            add_edge(b.index, label_block[last.label], "true")  # type: ignore[index]
            add_edge(b.index, label_block[last.label2], "false")  # type: ignore[index]
        elif last is not None and last.op == "RET":
            b.exits = True
        elif b.index + 1 < len(blocks):
            add_edge(b.index, b.index + 1, "fallthrough")
        else:
            b.exits = True
    # reachability
    seen: Set[int] = set()
    stack = [0] if blocks else []
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        stack.extend(t for t, _ in blocks[x].succ)
    for b in blocks:
        b.reachable = b.index in seen
    # reverse postorder over reachable blocks
    post: List[int] = []
    visited: Set[int] = set()

    def dfs(x: int):
        visited.add(x)
        for t, _ in blocks[x].succ:
            if t not in visited:
                dfs(t)
        post.append(x)

    import sys
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 5000))
    try:
        if blocks:
            dfs(0)
    finally:
        sys.setrecursionlimit(old)
    rpo = list(reversed(post))
    # dominators (iterative)
    reach = [b.index for b in blocks if b.reachable]
    dom: Dict[int, Set[int]] = {x: set(reach) for x in reach}
    if reach:
        dom[0] = {0}
    changed = True
    while changed:
        changed = False
        for x in rpo:
            if x == 0:
                continue
            preds = [p for p in blocks[x].pred if blocks[p].reachable]
            new = set.intersection(*(dom[p] for p in preds)) | {x} if preds else {x}
            if new != dom[x]:
                dom[x] = new
                changed = True
    # back edges & natural loops
    back: Dict[int, List[int]] = {}
    for b in blocks:
        if not b.reachable:
            continue
        for t, _ in b.succ:
            if t in dom.get(b.index, set()):
                back.setdefault(t, []).append(b.index)
    loops: List[Loop] = []
    for header in sorted(back):
        body = {header}
        work = [s for s in back[header]]
        while work:
            x = work.pop()
            if x in body:
                continue
            body.add(x)
            work.extend(p for p in blocks[x].pred if blocks[p].reachable)
        loops.append(Loop(header, sorted(back[header]), sorted(body)))
    for l in loops:
        l.depth = 1 + sum(1 for o in loops if o is not l and l.header in o.body and o.header != l.header)
    back_pairs = {(s, h) for h, srcs in back.items() for s in srcs}
    for b in blocks:
        for t, kind in b.succ:
            edges.append({"from": b.id, "to": f"B{t}", "kind": kind, "isBackEdge": (b.index, t) in back_pairs})
    return FunctionCFG(fn.name, blocks, edges, loops, dom, rpo)


@dataclass
class CFGResult:
    functions: List[FunctionCFG]
    build_ms: float

    def to_dict(self) -> dict:
        fns = [f.to_dict() for f in self.functions]
        tot = {"blocks": 0, "edges": 0, "branches": 0, "loops": 0, "unreachableBlocks": 0}
        for f in fns:
            for k in tot:
                tot[k] += f["statistics"][k]
        tot["functions"] = len(fns)
        tot["maxLoopDepth"] = max((f["statistics"]["maxLoopDepth"] for f in fns), default=0)
        tot["cyclomaticComplexity"] = sum(f["statistics"]["cyclomaticComplexity"] for f in fns)
        return {"functions": fns, "statistics": tot, "buildMs": round(self.build_ms, 4)}


def build_cfg(program: IRProgram) -> CFGResult:
    t0 = time.perf_counter()
    fns = [build_function_cfg(f) for f in program.functions]
    return CFGResult(fns, (time.perf_counter() - t0) * 1000)
