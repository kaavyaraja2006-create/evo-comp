from compiler.digital_twin.twin import DigitalTwin
from compiler.evolution.baseline import run_baseline_comparison
from compiler.evolution.engine import EvolutionConfig
from .conftest import full_ir

NEGATIVE_DIV_SRC = (
    "int fact(int n) { if (n < 2) { return 1; } return n * fact(n - 1); }\n"
    "int main() { int x = -9; print(x / 4); print(fact(6)); }"
)


def test_baseline_comparison_runs_both_searches_and_reports_real_fields():
    ir = full_ir(NEGATIVE_DIV_SRC)
    twin = DigitalTwin(ir, seed=42)
    cfg = EvolutionConfig(seed=42, population=16, generations=14)
    result = run_baseline_comparison(ir, twin, cfg)

    assert result["seed"] == 42
    assert result["original"]["staticSize"] == ir.instr_count()
    assert result["original"]["dynamicCost"] == twin.reference.cost
    assert set(result["gated"].keys()) >= {"label", "found"}
    assert set(result["ungated"].keys()) >= {"label", "found"}
    assert "headline" in result and isinstance(result["headline"], str)
    assert "methodology" in result
    # both searches must have really executed candidates through the twin
    assert result["gatedStatistics"]["totalCandidates"] > 0
    assert result["ungatedStatistics"]["totalCandidates"] > 0


def test_baseline_comparison_ungated_winner_correctness_is_a_real_measurement():
    """Whatever the ungated search picks, `actuallyCorrect` must reflect that
    specific candidate's real Digital Twin status, not be assumed true."""
    ir = full_ir(NEGATIVE_DIV_SRC)
    twin = DigitalTwin(ir, seed=42)
    cfg = EvolutionConfig(seed=42, population=16, generations=14)
    result = run_baseline_comparison(ir, twin, cfg)
    if result["ungated"]["found"]:
        assert isinstance(result["ungated"]["actuallyCorrect"], bool)
        # incorrectCandidateWouldShip is only true when the ungated winner is
        # both different from the gated winner AND actually incorrect
        if result["incorrectCandidateWouldShip"]:
            assert result["ungated"]["actuallyCorrect"] is False
            assert result["ungated"]["candidateId"] != result["gated"]["candidateId"]


def test_baseline_comparison_finds_a_divergent_seed_for_the_negative_division_program():
    """At least one seed in a small sweep must show the Digital Twin actually
    preventing an incorrect program from being selected - this is the project's
    core novelty claim, and it must be demonstrable with real data, not just
    theoretically possible."""
    ir = full_ir(NEGATIVE_DIV_SRC)
    found_divergence = False
    for seed in (1, 2, 3, 7, 11, 13):
        twin = DigitalTwin(ir, seed=seed)
        cfg = EvolutionConfig(seed=seed, population=16, generations=16)
        result = run_baseline_comparison(ir, twin, cfg)
        if result["incorrectCandidateWouldShip"]:
            found_divergence = True
            break
    assert found_divergence, "expected at least one seed to show a real gated-vs-ungated divergence"
