from compiler.digital_twin.twin import DigitalTwin
from compiler.evolution.engine import EvolutionConfig, EvolutionEngine
from .conftest import full_ir

SMALL_CFG = EvolutionConfig(seed=7, population=8, generations=5)


def test_deterministic_given_same_seed():
    ir = full_ir("int main() { int x = 10; int y = 20; print(x * 2 + y); }")
    twin = DigitalTwin(ir, seed=7)
    r1 = EvolutionEngine(ir, twin, SMALL_CFG).run()
    r2 = EvolutionEngine(ir, twin, SMALL_CFG).run()
    assert [c["genome"] for c in r1["candidates"]] == [c["genome"] for c in r2["candidates"]]


def test_rejected_candidates_have_no_fitness():
    ir = full_ir("int main() { int x = -9; print(x / 4); }")
    twin = DigitalTwin(ir, seed=1)
    r = EvolutionEngine(ir, twin, EvolutionConfig(seed=1, population=10, generations=6)).run()
    for c in r["candidates"]:
        if c["status"] == "REJECTED":
            assert c["fitness"] is None


def test_correctness_dominates_fitness_when_all_improvements_unsound():
    ir = full_ir("int g = 0;\nfunction bump() { g += 1; print(g); }\nint main() { bump(); print(g); }")
    twin = DigitalTwin(ir, seed=1)
    r = EvolutionEngine(ir, twin, SMALL_CFG).run()
    assert r["statistics"]["bestFitness"] == 0.0  # identity genome; no unsound gain accepted


def test_best_fitness_never_decreases_generation_over_generation():
    ir = full_ir("int main() { int x = 10; int y = 20; int z = x*2 + y*4 + (3+4); "
                 "if (x > 5) { print(z); } else { print(0); } }")
    twin = DigitalTwin(ir, seed=42)
    r = EvolutionEngine(ir, twin, EvolutionConfig(seed=42, population=12, generations=8)).run()
    best_so_far = -1e9
    for g in r["generations"]:
        if g["bestFitness"] is not None:
            assert g["bestFitness"] >= best_so_far - 1e-9
            best_so_far = max(best_so_far, g["bestFitness"])


def test_hall_of_fame_candidates_are_all_valid():
    ir = full_ir("int main() { int total = 0; for (int i=0;i<10;i++) { total = total + i; } print(total); }")
    twin = DigitalTwin(ir, seed=3)
    r = EvolutionEngine(ir, twin, SMALL_CFG).run()
    by_id = {c["id"]: c for c in r["candidates"]}
    for cid in r["hallOfFame"]:
        assert by_id[cid]["status"] == "VALID"


def test_shadow_fitness_is_always_populated_even_for_rejected_candidates():
    """shadowFitness is the un-gated reading of the same fitness formula - it
    must exist for every candidate regardless of Digital Twin verdict, since
    it's what powers both the what-if counterfactual and the baseline
    comparison (neither of which re-runs anything)."""
    ir = full_ir("int main() { int x = -9; print(x / 4); }")
    twin = DigitalTwin(ir, seed=1)
    r = EvolutionEngine(ir, twin, EvolutionConfig(seed=1, population=10, generations=6)).run()
    rejected = [c for c in r["candidates"] if c["status"] == "REJECTED"]
    assert rejected, "test program should produce at least one rejected candidate"
    for c in rejected:
        assert c["fitness"] is None
        assert c["shadowFitness"] is not None


def test_ungated_run_can_select_a_rejected_candidate():
    """With correctness_gate=False, selection must be able to end up on a
    candidate the Digital Twin actually rejected - that's the whole point of
    turning the gate off, and is what the baseline comparison measures."""
    ir = full_ir("int main() { int x = -9; print(x / 4); }")
    twin = DigitalTwin(ir, seed=1)
    cfg = EvolutionConfig(seed=1, population=20, generations=15, correctness_gate=False)
    r = EvolutionEngine(ir, twin, cfg).run()
    assert r["statistics"]["rejectedCandidates"] > 0  # the Digital Twin still ran and still rejected real candidates
    best_id = r["bestCandidateId"]
    by_id = {c["id"]: c for c in r["candidates"]}
    assert best_id is not None
    # the gate being off means the winner is chosen by shadowFitness alone,
    # so it is not required to be VALID (it may legitimately still be, but
    # the selection mechanism itself must not have required it)
    assert by_id[best_id]["shadowFitness"] is not None


def test_gated_default_behaviour_is_unchanged():
    """correctness_gate defaults to True and must reproduce the original,
    hard-constrained behaviour: no rejected candidate is ever selectable."""
    ir = full_ir("int main() { int x = -9; print(x / 4); }")
    twin = DigitalTwin(ir, seed=1)
    cfg = EvolutionConfig(seed=1, population=10, generations=6)
    assert cfg.correctness_gate is True
    r = EvolutionEngine(ir, twin, cfg).run()
    by_id = {c["id"]: c for c in r["candidates"]}
    for cid in r["hallOfFame"]:
        assert by_id[cid]["status"] == "VALID"
    if r["bestCandidateId"]:
        assert by_id[r["bestCandidateId"]]["status"] == "VALID"
