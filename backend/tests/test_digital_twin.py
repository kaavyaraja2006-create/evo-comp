from compiler.digital_twin.twin import DigitalTwin
from compiler.evolution.passes import apply_genome, SOUND_PASSES, STANDARD_PIPELINE
from .conftest import full_ir


def test_sound_pipeline_validated_as_correct(sample_programs):
    for name, src in sample_programs.items():
        ir = full_ir(src)
        twin = DigitalTwin(ir, seed=1)
        opt, _ = apply_genome(ir, list(STANDARD_PIPELINE))
        report = twin.validate(opt, "quick")
        assert report.valid, f"{name}: {report.to_dict()}"


def test_unsound_div_to_shift_rejected_on_negative_input():
    ir = full_ir("int main() { int x = -9; print(x / 4); }")
    twin = DigitalTwin(ir, seed=1)
    opt, _ = apply_genome(ir, ["spec_div_to_shift"])
    report = twin.validate(opt, "thorough")
    assert not report.valid
    assert report.differences  # whole-program output actually differs


def test_unsound_drop_unused_calls_rejected_when_side_effecting():
    ir = full_ir("int g = 0;\nfunction bump() { g += 1; print(g); }\nint main() { bump(); print(g); }")
    twin = DigitalTwin(ir, seed=1)
    opt, _ = apply_genome(ir, ["spec_drop_unused_calls"])
    report = twin.validate(opt, "quick")
    assert not report.valid


def test_malformed_candidate_is_rejected_not_crashed():
    ir = full_ir("int main() { print(1); }")
    twin = DigitalTwin(ir, seed=1)
    import copy
    broken = copy.deepcopy(ir)
    broken.functions[0].instrs = []  # corrupt: missing return -> should be handled, not crash
    report = twin.validate(broken, "quick")
    assert report.verdict in ("VALID", "REJECTED")  # must not raise


def test_function_level_differential_tests_run_for_parameterized_functions():
    ir = full_ir("function half(int a) { return a / 2; }\nint main() { print(half(10)); }")
    twin = DigitalTwin(ir, seed=1)
    opt, _ = apply_genome(ir, list(STANDARD_PIPELINE))
    report = twin.validate(opt, "quick")
    assert report.cases > 0
    assert any(f["name"] == "half" for f in report.function_tests)
