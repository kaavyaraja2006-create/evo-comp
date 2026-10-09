from .conftest import full_cfg


def test_loop_detected_with_correct_header():
    c = full_cfg("int main() { int t = 0; for (int i = 0; i < 10; i++) { t = t + i; } print(t); }")
    main_cfg = c.fn("main") if hasattr(c, "fn") else next(f for f in c.functions if f.name == "main")
    assert len(main_cfg.loops) == 1


def test_nested_loop_depth():
    c = full_cfg("int main() { int t = 0; for (int i=0;i<3;i++) { for (int j=0;j<3;j++) { t=t+1; } } print(t); }")
    main_cfg = next(f for f in c.functions if f.name == "main")
    assert max(l.depth for l in main_cfg.loops) == 2


def test_reachability_flags_dead_block():
    c = full_cfg("int main() { print(1); return 0; print(2); }")
    main_cfg = next(f for f in c.functions if f.name == "main")
    assert any(not b.reachable for b in main_cfg.blocks)


def test_every_block_reachable_in_straight_line_program():
    c = full_cfg("int main() { int x = 1; int y = 2; print(x + y); }")
    main_cfg = next(f for f in c.functions if f.name == "main")
    assert all(b.reachable for b in main_cfg.blocks)
    assert main_cfg.stats()["cyclomaticComplexity"] == 1


def test_branch_increases_cyclomatic_complexity():
    c = full_cfg("int main() { if (1 < 2) { print(1); } else { print(2); } }")
    main_cfg = next(f for f in c.functions if f.name == "main")
    assert main_cfg.stats()["cyclomaticComplexity"] == 2


def test_dominators_computed_for_entry():
    c = full_cfg("int main() { if (1 < 2) { print(1); } print(2); }")
    main_cfg = next(f for f in c.functions if f.name == "main")
    assert main_cfg.dominators[0] == {0}
