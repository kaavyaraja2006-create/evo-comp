"""AST finalisation: ids, parents, depth, invariants, serialisation."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .nodes import Node, Program, walk


@dataclass
class ASTResult:
    root: Program
    nodes: Dict[int, Node] = field(default_factory=dict)
    parent: Dict[int, Optional[int]] = field(default_factory=dict)
    depth: Dict[int, int] = field(default_factory=dict)
    order: List[int] = field(default_factory=list)
    invariants: List[dict] = field(default_factory=list)
    build_ms: float = 0.0

    def node_count(self) -> int:
        return len(self.nodes)

    def to_dict(self) -> dict:
        flat = []
        for nid in self.order:
            n = self.nodes[nid]
            flat.append({
                "id": nid,
                "type": n.node_type,
                "label": n.label(),
                "attributes": n.attributes(),
                "parent": self.parent[nid],
                "depth": self.depth[nid],
                "children": [{"role": role, "id": c.id} for role, c in n.children()],
                "loc": n.span.to_dict(),
            })
        counts = Counter(n.node_type for n in self.nodes.values())
        leaves = sum(1 for n in self.nodes.values() if not n.children())
        return {
            "root": self.root.id,
            "nodes": flat,
            "statistics": {
                "nodeCount": len(self.nodes),
                "maxDepth": max(self.depth.values()) if self.depth else 0,
                "leafCount": leaves,
                "byType": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))),
            },
            "invariants": self.invariants,
            "buildMs": round(self.build_ms, 4),
        }


def build_ast(program: Program) -> ASTResult:
    """Assign preorder ids and verify structural invariants.

    Invariants are *actually checked* on the tree and reported; if one fails
    the stage fails (it would indicate a parser bug)."""
    t0 = time.perf_counter()
    res = ASTResult(root=program)
    stack = [(program, None, 0)]
    next_id = 0
    # iterative preorder so deep trees can't blow the recursion limit
    while stack:
        node, parent, depth = stack.pop()
        node.id = next_id
        next_id += 1
        res.nodes[node.id] = node
        res.parent[node.id] = parent
        res.depth[node.id] = depth
        res.order.append(node.id)
        for _, child in reversed(node.children()):
            stack.append((child, node.id, depth + 1))

    def check(name: str, ok: bool, detail: str = ""):
        res.invariants.append({"name": name, "passed": bool(ok), "detail": detail})

    ids = [n.id for n in walk(program)]
    check("unique node ids", len(ids) == len(set(ids)))
    check("single root without parent", res.parent[program.id] is None and
          sum(1 for p in res.parent.values() if p is None) == 1)
    bad_span = [n.id for n in res.nodes.values()
                if n.node_type != "Program" and res.parent[n.id] is not None
                and not (res.nodes[res.parent[n.id]].span.start <= n.span.start
                         and n.span.end <= res.nodes[res.parent[n.id]].span.end)]
    check("child spans lie within parent spans", not bad_span,
          f"violations: {bad_span[:5]}" if bad_span else "")
    check("every non-root node has exactly one parent",
          all(res.parent[i] is not None for i in res.nodes if i != program.id))
    res.build_ms = (time.perf_counter() - t0) * 1000
    return res
