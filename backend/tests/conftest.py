"""Shared fixtures/helpers for the compiler-stage test suites."""

from __future__ import annotations

import pytest

from lexer.lexer import Lexer
from compiler.ast.builder import build_ast
from compiler.cfg.builder import build_cfg
from compiler.codegen.generator import generate_bytecode
from compiler.digital_twin.twin import DigitalTwin
from compiler.evolution.engine import EvolutionConfig, EvolutionEngine
from compiler.evolution.passes import apply_genome, count_opportunities
from compiler.evm.machine import EvoVM
from compiler.evm.verifier import verify
from compiler.ir.generator import generate_ir
from compiler.ir.interpreter import run_program
from compiler.parser.parser import parse_tokens
from compiler.semantic.analyzer import analyze


def lex(src: str):
    return Lexer(src).tokenize().tokens


def parse(src: str):
    return parse_tokens(lex(src))


def full_ast(src: str):
    r = parse(src)
    assert r.success, r.errors
    return build_ast(r.program)


def full_semantic(src: str):
    a = full_ast(src)
    return a, analyze(a)


def full_ir(src: str):
    a, s = full_semantic(src)
    assert s.success, s.diagnostics
    ir, _ = generate_ir(a, s)
    return ir


def full_cfg(src: str):
    return build_cfg(full_ir(src))


@pytest.fixture
def sample_programs():
    return {
        "loop_sum": "int main() { int total = 0; for(int i = 0; i < 10; i++) { total = total + i; } print(total); }",
        "function_call": "function add(int a, int b) { return a + b; }\n"
                         "int main() { int result = add(10, 20); print(result); }",
        "mixed_arithmetic": "int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }\n"
                            "int main() { int x = -7; print(x/2); print(x%2); print(fib(10)); "
                            "int z = 0; print(1/z); }",
        "multiple_void_calls": "function noisy(int a) { print(a); }\n"
                               "int main() { noisy(3); noisy(4); noisy(5); }",
    }
