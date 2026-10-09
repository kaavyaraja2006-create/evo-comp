from .conftest import parse


def test_valid_programs_parse(sample_programs):
    for name, src in sample_programs.items():
        r = parse(src)
        assert r.success, f"{name}: {r.errors}"
        assert r.node_count > 0


def test_syntax_error_missing_semicolon():
    r = parse("int x = 5\nprint(x);")
    assert not r.success
    e = r.errors[0]
    assert e["expected"] == "';'"
    assert e["line"] == 2  # error surfaces at the token that breaks the grammar


def test_syntax_error_missing_expression():
    r = parse("int x = ;")
    assert not r.success
    assert r.errors[0]["expected"] == "expression"


def test_syntax_error_unclosed_block():
    r = parse("int main() { int x = 1;")
    assert not r.success
    assert any("}" in e["expected"] for e in r.errors)


def test_multiple_errors_recovered_in_one_pass():
    r = parse("int x = ;\nint y = ;\nint z = ;")
    assert not r.success
    assert len(r.errors) == 3  # panic-mode recovery finds all three, not just the first


def test_nested_function_declaration_rejected():
    r = parse("int main() { int f() { return 1; } }")
    assert not r.success
    assert any("top level" in e["message"] for e in r.errors)


def test_else_without_if_rejected():
    r = parse("int main() { else { } }")
    assert not r.success


def test_comments_are_skipped_and_counted():
    r = parse("// comment\nint main() { /* c */ print(1); }")
    assert r.success
    assert r.comments_skipped == 2


def test_operator_precedence_shape():
    r = parse("int main() { int x = 1 + 2 * 3; print(x); }")
    assert r.success
    prog = r.program
    decl = prog.body[0].body.statements[0]
    add = decl.init
    assert add.operator == "+"
    assert add.right.operator == "*"  # multiplication binds tighter, nested on the right


def test_function_call_and_typed_vs_untyped_forms():
    r = parse("function f(int a) { return a; }\nint g(int a) { return a; }\nint main() { print(f(1) + g(2)); }")
    assert r.success
    fns = [n for n in r.program.body if n.node_type == "FunctionDeclaration"]
    assert fns[0].form == "function" and fns[0].return_type is None
    assert fns[1].form == "typed" and fns[1].return_type == "int"


def test_array_syntax_rejected():
    # Arrays are not part of the EvoLang grammar; '[' is simply not a valid
    # continuation of a variable declaration.
    r = parse("int main() { int a[3]; }")
    assert not r.success
    assert r.errors[0]["found"] == "["


def test_bracket_as_a_primary_expression_gets_the_dedicated_message():
    # '[' cannot start a primary expression; that specific case gets the
    # dedicated explanatory message (mid-expression, after a completed
    # primary, it instead surfaces as a normal "expected X" parse error).
    r = parse("int main() { print([1]); }")
    assert not r.success
    assert any("array" in e["message"].lower() for e in r.errors)


def test_rule_counts_and_trace_present():
    r = parse("int main() { print(1); }")
    assert r.success
    assert r.rule_counts.get("program") == 1
    assert any(t["rule"] == "printStmt" for t in r.trace)
