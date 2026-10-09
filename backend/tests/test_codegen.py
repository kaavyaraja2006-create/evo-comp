from compiler.codegen.generator import generate_bytecode
from compiler.evm.machine import EvoVM
from compiler.evm.verifier import verify
from compiler.evolution.passes import STANDARD_PIPELINE, apply_genome
from compiler.ir.interpreter import run_program
from .conftest import full_ir


def _matches(src, genome=None):
    ir = full_ir(src)
    prog = apply_genome(ir, genome)[0] if genome else ir
    ref = run_program(prog)
    bp, _ = generate_bytecode(prog)
    v = verify(bp)
    assert v["ok"], v["errors"]
    r = EvoVM(bp).run()
    assert (r.status == "HALTED") == (ref.status == "OK")
    assert r.output == ref.output
    return ref, r


def test_bytecode_matches_ir_interpreter_on_all_sample_programs(sample_programs):
    for name, src in sample_programs.items():
        _matches(src)
        _matches(src, list(STANDARD_PIPELINE))


def test_verifier_catches_bad_jump_target():
    from compiler.codegen.bytecode import BInstr, BFunction, BProgram
    code = [BInstr(0, "PUSH", 1), BInstr(1, "JUMP", 99), BInstr(2, "RETURN")]
    fn = BFunction("f", 0, 3, 0, 0, [], "int")
    p = BProgram(code, {"f": fn}, [])
    v = verify(p)
    assert not v["ok"]


def test_verifier_catches_arity_mismatch():
    from compiler.codegen.bytecode import BInstr, BFunction, BProgram
    code = [BInstr(0, "CALL", "g", 2), BInstr(1, "RETURN_VOID")]
    fn = BFunction("f", 0, 2, 0, 0, [], "void")
    g = BFunction("g", 2, 2, 1, 1, ["a"], "void")
    p = BProgram(code, {"f": fn, "g": g}, [])
    v = verify(p)
    assert not v["ok"]
    assert any("arg" in e for e in v["errors"])


def test_recursive_division_by_zero_matches_across_engines():
    ref, r = _matches("int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }\n"
                      "int main() { print(fib(6)); int z = 0; print(1/z); }")
    assert ref.status == "RUNTIME_ERROR" and r.status == "RUNTIME_ERROR"
    assert ref.error_kind == r.error_kind
