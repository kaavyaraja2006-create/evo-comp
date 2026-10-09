from .conftest import full_semantic


def _errs(src):
    _, s = full_semantic(src)
    return s


def test_valid_programs_have_no_errors(sample_programs):
    for name, src in sample_programs.items():
        s = _errs(src)
        assert s.success, f"{name}: {s.diagnostics}"


def test_type_mismatch_detected():
    s = _errs('int x = 10;\nfloat y = x + "hi";\nprint(y);')
    assert not s.success
    assert any(d["code"] == "E004" for d in s.diagnostics)


def test_duplicate_declaration_detected():
    s = _errs("int main() { int q = 1; int q = 2; print(q); }")
    assert not s.success
    assert any(d["code"] == "E002" for d in s.diagnostics)


def test_undeclared_identifier_detected():
    s = _errs("int main() { print(undefined_var); }")
    assert not s.success
    assert any(d["code"] == "E001" for d in s.diagnostics)


def test_undeclared_identifier_notes_out_of_scope_var():
    s = _errs("int main() { for (int i = 0; i < 3; i++) { } print(i); }")
    assert not s.success
    e = next(d for d in s.diagnostics if d["code"] == "E001")
    assert "not visible here" in e["message"]


def test_wrong_argument_count_detected():
    s = _errs("int f(int a) { return a; }\nint main() { int z = f(1, 2); print(z); }")
    assert not s.success
    assert any(d["code"] == "E007" for d in s.diagnostics)


def test_wrong_argument_type_detected():
    s = _errs('int f(int a) { return a; }\nint main() { int z = f("hi"); print(z); }')
    assert not s.success
    assert any(d["code"] == "E008" for d in s.diagnostics)


def test_self_recursive_untyped_function_requires_explicit_type():
    s = _errs("function fact(int n) { if (n < 2) { return 1; } return n * fact(n-1); }")
    assert not s.success
    assert any(d["code"] == "E015" for d in s.diagnostics)


def test_self_recursive_typed_function_is_fine():
    s = _errs("int fact(int n) { if (n < 2) { return 1; } return n * fact(n-1); }\n"
              "int main() { print(fact(5)); }")
    assert s.success


def test_division_by_constant_zero_flagged():
    s = _errs("int main() { int x = 1 / 0; print(x); }")
    assert not s.success
    assert any(d["code"] == "E011" for d in s.diagnostics)


def test_unused_variable_warning():
    s = _errs("int main() { int unused = 5; print(1); }")
    assert s.success
    assert any(d["code"] == "W001" for d in s.diagnostics)


def test_shadowing_warning():
    s = _errs("int main() { int x = 1; { int x = 2; print(x); } print(x); }")
    assert s.success
    assert any(d["code"] == "W004" for d in s.diagnostics)


def test_unreachable_code_warning():
    s = _errs("int f() { return 1; print(2); }\nint main() { print(f()); }")
    assert s.success
    assert any(d["code"] == "W002" for d in s.diagnostics)


def test_main_with_parameters_rejected():
    s = _errs("int main(int argc) { print(argc); }")
    assert not s.success
    assert any(d["code"] == "E014" for d in s.diagnostics)


def test_implicit_int_to_float_widening_allowed():
    s = _errs("int main() { float x = 5; print(x); }")
    assert s.success
    assert s.implicit_conversions >= 1


def test_forward_call_to_later_function_resolves():
    s = _errs("int main() { print(helper(3)); }\nint helper(int a) { return a * 2; }")
    assert s.success
