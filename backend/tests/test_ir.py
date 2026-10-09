from .conftest import full_ir
from compiler.ir.interpreter import run_program


def test_loop_sum_produces_correct_output(sample_programs):
    ir = full_ir(sample_programs["loop_sum"])
    r = run_program(ir)
    assert r.status == "OK"
    assert r.output == ["45"]


def test_function_call_produces_correct_output(sample_programs):
    ir = full_ir(sample_programs["function_call"])
    r = run_program(ir)
    assert r.status == "OK" and r.output == ["30"]


def test_short_circuit_and_does_not_evaluate_right_side():
    ir = full_ir('int calls = 0;\nfunction sideeffect() { calls += 1; return true; }\n'
                 'int main() { bool b = false && sideeffect(); print(calls); }')
    r = run_program(ir)
    assert r.output == ["0"]  # right side never evaluated


def test_short_circuit_or_does_not_evaluate_right_side():
    ir = full_ir('int calls = 0;\nfunction sideeffect() { calls += 1; return true; }\n'
                 'int main() { bool b = true || sideeffect(); print(calls); }')
    r = run_program(ir)
    assert r.output == ["0"]


def test_truncating_division_and_sign_of_mod():
    ir = full_ir("int main() { print(-7/2); print(-7%2); print(7/-2); }")
    r = run_program(ir)
    assert r.output == ["-3", "-1", "-3"]


def test_division_by_zero_is_runtime_error_after_prior_output():
    ir = full_ir("int main() { print(1); int z = 0; print(2/z); }")
    r = run_program(ir)
    assert r.status == "RUNTIME_ERROR"
    assert r.error_kind == "DivisionByZero"
    assert r.output == ["1"]  # output before the fault is preserved


def test_int_wraps_to_32_bits():
    ir = full_ir("int main() { int x = 2147483647; x = x + 1; print(x); }")
    r = run_program(ir)
    assert r.output == ["-2147483648"]


def test_string_concatenation():
    ir = full_ir('int main() { print("a" + "b" + "c"); }')
    r = run_program(ir)
    assert r.output == ["abc"]


def test_recursive_function_and_step_limit():
    ir = full_ir("int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }\n"
                 "int main() { print(fib(10)); }")
    r = run_program(ir)
    assert r.output == ["55"]
    r2 = run_program(ir, step_limit=5)
    assert r2.status == "STEP_LIMIT"
