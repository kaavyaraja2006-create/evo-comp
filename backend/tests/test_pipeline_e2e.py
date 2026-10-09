"""End-to-end tests: full 13-stage pipeline on the required test programs."""

import pytest

from pipeline.pipeline import STAGES, run_all, run_stage
from pipeline.session import CompileOptions, CompilationSession, StageBlocked

FAST = CompileOptions(seed=42, population=8, generations=5, step_limit=50_000)

PROGRAMS = {
    "loop_sum": "int main() { int total = 0; for(int i = 0; i < 10; i++) { total = total + i; } print(total); }",
    "function_call": "function add(int a, int b) { return a + b; }\n"
                     "int main() { int result = add(10, 20); print(result); }",
    "mixed_arithmetic": "int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }\n"
                        "int main() { int x = -7; print(x/2); print(x%2); print(fib(10)); "
                        "int z = 0; print(1/z); }",
    "multiple_void_calls": "function noisy(int a) { print(a); }\n"
                           "int main() { noisy(3); noisy(4); noisy(5); }",
    "function_plus_loop": "function add(int a, int b) { return a + b; }\n"
                          "int main() { int t = 0; for(int i = 0; i < 10; i++) { t = t + add(i, 2*4); } print(t); }",
}


@pytest.mark.parametrize("name", PROGRAMS)
def test_all_stages_complete_for_required_programs(name):
    s = CompilationSession(PROGRAMS[name], FAST)
    failed_at = run_all(s)
    assert failed_at is None, f"{name} failed at {failed_at}: {s.stages[failed_at].error}"
    for stage in STAGES:
        assert s.stages[stage].status == "completed"


@pytest.mark.parametrize("name", PROGRAMS)
def test_final_validation_reports_equivalence(name):
    s = CompilationSession(PROGRAMS[name], FAST)
    run_all(s)
    val = s.stages["validation"].data
    assert val["equivalent"] is True


def test_lexical_error_stops_pipeline_at_lexer():
    s = CompilationSession("int x = 5; @@@", FAST)
    failed_at = run_all(s)
    assert failed_at == "lexer"
    assert s.stages["parser"].status == "not_started"


def test_syntax_error_stops_pipeline_at_parser():
    s = CompilationSession("int x = ;", FAST)
    failed_at = run_all(s)
    assert failed_at == "parser"


def test_semantic_error_stops_pipeline_at_semantic():
    s = CompilationSession("int main() { print(undeclared); }", FAST)
    failed_at = run_all(s)
    assert failed_at == "semantic"


def test_running_a_stage_out_of_order_is_blocked():
    s = CompilationSession("int main() { print(1); }", FAST)
    with pytest.raises(StageBlocked):
        run_stage(s, "ir")


def test_rerunning_earlier_stage_invalidates_downstream():
    s = CompilationSession("int main() { int x = 1; print(x); }", FAST)
    run_all(s)
    assert s.stages["validation"].status == "completed"
    run_stage(s, "parser")
    assert s.stages["validation"].status == "not_started"
    assert s.stages["ir"].status == "not_started"


def test_report_only_contains_values_traceable_to_stage_data():
    s = CompilationSession(PROGRAMS["function_plus_loop"], FAST)
    run_all(s)
    report = s.stages["validation"].data["report"]
    assert report["ir"]["instructions"] == s.stages["ir"].data["instructionCount"]
    assert report["cfg"]["blocks"] == s.stages["cfg"].data["statistics"]["blocks"]
    assert report["semanticAnalysis"]["symbols"] == s.stages["semantic"].data["statistics"]["symbolCount"]


def test_report_surfaces_digital_twin_impact_and_pass_usage_traceable_to_stage_data():
    """The rejection-rate / what-if / pass-proposal-frequency additions must be
    the same objects the twin/evolution stages actually produced, not a
    recomputed or re-described version of them."""
    s = CompilationSession(PROGRAMS["mixed_arithmetic"], FAST)
    run_all(s)
    report = s.stages["validation"].data["report"]
    twin_data = s.stages["twin"].data
    evo_data = s.stages["evolution"].data

    assert report["digitalTwin"]["impact"] is twin_data["digitalTwinImpact"]
    assert report["passUsage"] is evo_data["passUsage"]

    impact = report["digitalTwin"]["impact"]
    assert impact["candidatesEvaluated"] == len(evo_data["candidates"])
    assert 0.0 <= impact["rejectionRate"] <= 1.0
    assert isinstance(impact["headline"], str) and impact["headline"]

    for name, usage in report["passUsage"].items():
        assert usage["proposed"] == usage["proposedValid"] + usage["proposedRejected"]


def test_evolution_dna_guidance_passes_carry_real_proposal_counts():
    s = CompilationSession(PROGRAMS["mixed_arithmetic"], FAST)
    run_all(s)
    evo = s.stages["evolution"].data
    usage = evo["passUsage"]
    for p in evo["dnaGuidance"]["passes"]:
        assert p["timesProposed"] == usage[p["name"]]["proposed"]
        assert p["timesInRejectedCandidate"] == usage[p["name"]]["proposedRejected"]
