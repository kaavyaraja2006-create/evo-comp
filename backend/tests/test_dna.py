from compiler.cfg.builder import build_cfg
from compiler.dna.extractor import extract_dna
from .conftest import full_ast, full_ir, full_semantic


def _dna(src):
    a, s = full_semantic(src)
    ir = full_ir(src)
    return extract_dna(src, a, s, ir, build_cfg(ir))


def test_dna_deterministic_for_same_source():
    src = "int main() { int x = 1; print(x); }"
    d1, d2 = _dna(src), _dna(src)
    assert d1["signatures"] == d2["signatures"]


def test_dna_signatures_differ_for_different_programs():
    d1 = _dna("int main() { int x = 1; print(x); }")
    d2 = _dna("int main() { int x = 2; print(x); }")
    assert d1["signatures"]["structural"] == d2["signatures"]["structural"]  # same shape
    assert d1["signatures"]["astFingerprint"] != d2["signatures"]["astFingerprint"]  # different literal


def test_dna_call_graph_and_recursion_detection():
    d = _dna("int fact(int n) { if (n < 2) { return 1; } return n * fact(n - 1); }\n"
             "int main() { print(fact(5)); }")
    assert "fact" in d["functionProfile"]["recursive"]
    assert d["functionProfile"]["callGraph"]["main"] == ["fact"]


def test_dna_loop_profile_counts_for_loop():
    d = _dna("int main() { int t = 0; for (int i=0;i<10;i++) { t = t + i; } print(t); }")
    assert d["loopProfile"]["forLoops"] == 1
    assert d["loopProfile"]["cfgLoops"] == 1


def test_dna_optimization_opportunities_nonzero_for_foldable_program():
    d = _dna("int main() { int x = 2 + 3 * 4; print(x); }")
    assert d["optimizationOpportunities"]["constant_folding"] > 0
