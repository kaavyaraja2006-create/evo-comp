from .conftest import full_ast


def test_ast_ids_are_unique_and_preorder():
    a = full_ast("int main() { int x = 1; print(x); }")
    ids = [n.id for n in a.nodes.values()]
    assert len(ids) == len(set(ids))
    assert a.order == sorted(a.order)


def test_ast_invariants_all_pass(sample_programs):
    from .conftest import full_ast as fa
    for src in sample_programs.values():
        a = fa(src)
        assert all(i["passed"] for i in a.invariants), a.invariants


def test_ast_statistics_by_type():
    a = full_ast("int main() { int x = 1; int y = 2; print(x + y); }")
    d = a.to_dict()
    assert d["statistics"]["byType"]["VariableDeclaration"] == 2
    assert d["statistics"]["nodeCount"] == a.node_count()


def test_ast_parent_child_consistency():
    a = full_ast("int main() { if (1 < 2) { print(1); } else { print(2); } }")
    for nid, n in a.nodes.items():
        for _, child in n.children():
            assert a.parent[child.id] == nid


def test_ast_depth_matches_nesting():
    a = full_ast("int main() { for (int i = 0; i < 1; i++) { if (i > 0) { print(i); } } }")
    depths = a.depth
    prog_depth = depths[a.root.id]
    deepest = max(depths.values())
    assert deepest > prog_depth + 3  # program -> fn -> block -> for -> block -> if -> block -> print
